"""SQLite 遗留数据一次性导入 PostgreSQL。"""

from __future__ import annotations

import json
import shutil
import sqlite3
import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from vnpy_ashare.storage.auth.migrate import PRIVATE_TABLES, migrate_user_scope_sqlite
from vnpy_ashare.storage.auth.users import create_user, users_table
from vnpy_common.auth.users import DEFAULT_USERNAME
from vnpy_common.paths import BACKUP_DIR, VNTRADER_DIR, get_app_db_path, get_chat_db_path
from vnpy_common.storage.config import require_database_url, resolve_database_url
from vnpy_common.storage.migrate import upgrade_head
from vnpy_common.storage.session import connect_app
from vnpy_common.storage.sqlite_backend import SqliteBackend

_DEFERRED_APP_TABLES: tuple[str, ...] = (
    "feed_item_reads",
    "trading_plan_symbols",
    "watchlist_group_members",
)
_APP_SCHEMA = "app"
_CHAT_SCHEMA = "chat"
_AUTH_SCHEMA = "auth"
_SYSTEM_SCHEMA = "system"
_CACHE_SCHEMA = "cache"

_AUTH_SQLITE_TABLES = frozenset({"users", "user_preferences"})
_CHAT_SQLITE_TABLES = frozenset({"sessions", "messages", "llm_turn_traces", "llm_tool_calls"})
_SKIP_SQLITE_TABLES = frozenset({"sqlite_sequence"})

_CACHE_SOURCES: tuple[tuple[str, str], ...] = (
    ("radar_predict_cache.db", "radar_predict_cache"),
    ("radar_horizon_cache.db", "radar_horizon_cache"),
    ("radar_ai_hint_cache.db", "radar_ai_hint_cache"),
    ("watchlist_signal_cache.db", "watchlist_signal_cache"),
    ("watchlist_position_cache.db", "watchlist_position_cache"),
    ("sector_flow_outlook_llm_cache.db", "sector_flow_outlook_llm_cache"),
)

# 旧版可能内嵌在 zak.db 的 cache 表（与独立 .db 二选一或并存，导入时 ON CONFLICT DO NOTHING）
_CACHE_APP_TABLES: tuple[str, ...] = (
    "watchlist_signal_cache",
    "watchlist_position_cache",
    "sector_flow_outlook_llm_cache",
)


@dataclass
class TableImportResult:
    schema: str
    table: str
    source: str
    rows_read: int = 0
    rows_inserted: int = 0
    skipped: bool = False
    note: str = ""


@dataclass
class ImportLegacyReport:
    target_user: str
    results: list[TableImportResult] = field(default_factory=list)
    archived: list[str] = field(default_factory=list)

    def summary_lines(self) -> list[str]:
        lines = [f"目标用户：{self.target_user}"]
        for item in self.results:
            if item.skipped:
                lines.append(f"  跳过 {item.schema}.{item.table} ({item.note})")
            else:
                lines.append(
                    f"  {item.schema}.{item.table}: 读取 {item.rows_read}，写入 {item.rows_inserted} [{item.source}]"
                )
        if self.archived:
            lines.append("已归档：")
            for path in self.archived:
                lines.append(f"  {path}")
        return lines


@dataclass
class ImportLegacyOptions:
    app_db: Path | None = None
    chat_db: Path | None = None
    username: str = DEFAULT_USERNAME
    dry_run: bool = False
    skip_cache: bool = False
    cache_only: bool = False
    archive: bool = False
    upgrade: bool = True


def normalize_user_id(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if len(text) == 32 and all(ch in "0123456789abcdefABCDEF" for ch in text):
        return str(uuid.UUID(hex=text))
    return text


def _now_iso() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _open_sqlite(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def _prepare_app_sqlite(conn: sqlite3.Connection) -> str:
    migrate_user_scope_sqlite(conn)
    conn.commit()
    row = conn.execute("SELECT id FROM users WHERE username = ?", (DEFAULT_USERNAME,)).fetchone()
    return str(row[0]) if row is not None else ""


def _sqlite_tables(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name",
    ).fetchall()
    return [str(row[0]) for row in rows if str(row[0]) not in _SKIP_SQLITE_TABLES]


def _sqlite_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    return SqliteBackend.table_columns(conn, table)


def _pg_columns(conn, schema: str, table: str) -> list[str]:
    rows = conn.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = ? AND table_name = ?
        ORDER BY ordinal_position
        """,
        (schema, table),
    ).fetchall()
    return [str(row["column_name"]) for row in rows]


def _pg_table_exists(conn, schema: str, table: str) -> bool:
    row = conn.execute(
        """
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = ? AND table_name = ?
        LIMIT 1
        """,
        (schema, table),
    ).fetchone()
    return row is not None


def _import_auth_users(
    sqlite_conn: sqlite3.Connection,
    pg_conn,
    *,
    dry_run: bool,
) -> tuple[dict[str, str], TableImportResult]:
    """SQLite users.id -> PG auth.users.id（按 username 对齐）。"""
    mapping: dict[str, str] = {}
    result = TableImportResult(schema=_AUTH_SCHEMA, table="users", source="sqlite")
    if "users" not in _sqlite_tables(sqlite_conn):
        result.skipped = True
        result.note = "SQLite 无 users 表"
        return mapping, result

    rows = sqlite_conn.execute(
        "SELECT id, username, display_name, password_hash, is_active, created_at, updated_at FROM users",
    ).fetchall()
    result.rows_read = len(rows)
    table = users_table()
    for row in rows:
        old_id = str(row["id"])
        username = str(row["username"])
        if dry_run:
            mapping[old_id] = normalize_user_id(old_id) or old_id
            continue
        existing = pg_conn.execute(
            f"SELECT id FROM {table} WHERE username = ?",
            (username,),
        ).fetchone()
        if existing is not None:
            new_id = str(existing["id"])
        else:
            new_id = str(uuid.uuid4())
            pg_conn.execute(
                f"""
                INSERT INTO {table} (id, username, display_name, password_hash, is_active, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (username) DO NOTHING
                """,
                (
                    new_id,
                    username,
                    str(row["display_name"] or username),
                    str(row["password_hash"]),
                    bool(row["is_active"]),
                    str(row["created_at"] or _now_iso()),
                    str(row["updated_at"] or _now_iso()),
                ),
            )
            refetch = pg_conn.execute(f"SELECT id FROM {table} WHERE username = ?", (username,)).fetchone()
            if refetch is not None:
                new_id = str(refetch["id"])
        mapping[old_id] = normalize_user_id(new_id)
    result.rows_inserted = len(mapping) if not dry_run else result.rows_read
    return mapping, result


def _resolve_target_user_id(
    pg_conn,
    *,
    username: str,
    user_map: dict[str, str],
    sqlite_default_id: str,
) -> str:
    if sqlite_default_id and sqlite_default_id in user_map:
        return user_map[sqlite_default_id]
    for mapped in user_map.values():
        if mapped:
            ref = pg_conn.execute(
                f"SELECT id FROM {users_table()} WHERE id = ? AND username = ?",
                (mapped, username),
            ).fetchone()
            if ref is not None:
                return str(ref["id"])
    row = pg_conn.execute(
        f"SELECT id FROM {users_table()} WHERE username = ?",
        (username,),
    ).fetchone()
    if row is not None:
        return str(row["id"])
    user = create_user(pg_conn, username=username, password="default", display_name="默认用户")
    return user.id


def _row_to_insert(
    row: sqlite3.Row,
    columns: Sequence[str],
    *,
    user_id_column: str | None,
    user_map: dict[str, str],
    default_user_id: str,
) -> tuple:
    values: list[object] = []
    for column in columns:
        if column not in row.keys():
            if column == "user_id":
                values.append(default_user_id)
            else:
                values.append(None)
            continue
        raw = row[column]
        if column == user_id_column:
            old = str(raw or "").strip()
            if not old:
                values.append(default_user_id)
            else:
                values.append(user_map.get(old, normalize_user_id(old) or default_user_id))
            continue
        if column == "value_json" and raw is not None and not isinstance(raw, (dict, list)):
            text = str(raw)
            try:
                json.loads(text)
            except json.JSONDecodeError:
                values.append(json.dumps({"text": text}))
                continue
        values.append(raw)
    return tuple(values)


def _copy_sqlite_table(
    sqlite_conn: sqlite3.Connection,
    pg_conn,
    *,
    sqlite_table: str,
    pg_schema: str,
    pg_table: str,
    source_label: str,
    user_map: dict[str, str],
    default_user_id: str,
    inject_user_id: bool,
    dry_run: bool,
) -> TableImportResult:
    result = TableImportResult(schema=pg_schema, table=pg_table, source=source_label)
    if not _pg_table_exists(pg_conn, pg_schema, pg_table):
        result.skipped = True
        result.note = "PG 表不存在"
        return result

    src_columns = _sqlite_columns(sqlite_conn, sqlite_table)
    if not src_columns:
        result.skipped = True
        result.note = "SQLite 表不存在"
        return result

    dst_columns = _pg_columns(pg_conn, pg_schema, pg_table)
    if not dst_columns:
        result.skipped = True
        result.note = "无法读取 PG 列"
        return result

    copy_columns = [col for col in dst_columns if col in src_columns or (inject_user_id and col == "user_id")]
    if inject_user_id and "user_id" in dst_columns and "user_id" not in copy_columns:
        copy_columns.append("user_id")

    if not copy_columns:
        result.skipped = True
        result.note = "无共有列"
        return result

    rows = sqlite_conn.execute(f"SELECT * FROM {sqlite_table}").fetchall()
    result.rows_read = len(rows)
    if dry_run or not rows:
        return result

    user_id_column = "user_id" if "user_id" in copy_columns else None
    placeholders = ", ".join("?" for _ in copy_columns)
    column_sql = ", ".join(copy_columns)
    qualified = f"{pg_schema}.{pg_table}"
    insert_sql = f"INSERT INTO {qualified} ({column_sql}) VALUES ({placeholders}) ON CONFLICT DO NOTHING"

    batch: list[tuple] = []
    for row in rows:
        batch.append(
            _row_to_insert(
                row,
                copy_columns,
                user_id_column=user_id_column,
                user_map=user_map,
                default_user_id=default_user_id,
            )
        )
    before = int(pg_conn.execute(f"SELECT COUNT(*) AS c FROM {qualified}").fetchone()["c"])
    pg_conn.executemany(insert_sql, batch)
    after = int(pg_conn.execute(f"SELECT COUNT(*) AS c FROM {qualified}").fetchone()["c"])
    result.rows_inserted = max(0, after - before)
    return result


def _import_scheduler_json(pg_conn, *, scheduler_json: Path, dry_run: bool) -> TableImportResult:
    result = TableImportResult(schema=_SYSTEM_SCHEMA, table="scheduler_config", source=str(scheduler_json))
    if not scheduler_json.is_file():
        result.skipped = True
        result.note = "文件不存在"
        return result
    try:
        payload = json.loads(scheduler_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        result.skipped = True
        result.note = "JSON 无效"
        return result
    if not isinstance(payload, dict):
        result.skipped = True
        result.note = "JSON 非对象"
        return result
    result.rows_read = 1
    if dry_run:
        return result
    text = json.dumps(payload, ensure_ascii=False)
    pg_conn.execute(
        """
        INSERT INTO system.scheduler_config (id, config_json, updated_at)
        VALUES ('default', ?::jsonb, now())
        ON CONFLICT (id) DO UPDATE SET config_json = EXCLUDED.config_json, updated_at = EXCLUDED.updated_at
        """,
        (text,),
    )
    result.rows_inserted = 1
    return result


def _import_app_db(
    path: Path,
    pg_conn,
    *,
    user_map: dict[str, str],
    default_user_id: str,
    dry_run: bool,
) -> list[TableImportResult]:
    results: list[TableImportResult] = []
    if not path.is_file():
        return results
    sqlite_conn = _open_sqlite(path)
    try:
        _prepare_app_sqlite(sqlite_conn)
        tables = [t for t in _sqlite_tables(sqlite_conn) if t not in _AUTH_SQLITE_TABLES]
        ordered = [t for t in tables if t not in _DEFERRED_APP_TABLES] + [
            t for t in _DEFERRED_APP_TABLES if t in tables
        ]
        for table in ordered:
            inject = table in PRIVATE_TABLES or table == "feed_item_reads"
            results.append(
                _copy_sqlite_table(
                    sqlite_conn,
                    pg_conn,
                    sqlite_table=table,
                    pg_schema=_APP_SCHEMA,
                    pg_table=table,
                    source_label=str(path),
                    user_map=user_map,
                    default_user_id=default_user_id,
                    inject_user_id=inject,
                    dry_run=dry_run,
                )
            )
    finally:
        sqlite_conn.close()
    return results


def _import_chat_db(
    path: Path,
    pg_conn,
    *,
    user_map: dict[str, str],
    default_user_id: str,
    dry_run: bool,
) -> list[TableImportResult]:
    results: list[TableImportResult] = []
    if not path.is_file():
        return results
    sqlite_conn = _open_sqlite(path)
    try:
        for table in ("sessions", "messages", "llm_turn_traces", "llm_tool_calls"):
            columns = SqliteBackend.table_columns(sqlite_conn, table)
            if not columns:
                continue
            if "user_id" not in columns:
                sqlite_conn.execute(f"ALTER TABLE {table} ADD COLUMN user_id TEXT NOT NULL DEFAULT ''")
                sqlite_conn.execute(
                    f"UPDATE {table} SET user_id = ? WHERE user_id = ''",
                    (default_user_id,),
                )
            results.append(
                _copy_sqlite_table(
                    sqlite_conn,
                    pg_conn,
                    sqlite_table=table,
                    pg_schema=_CHAT_SCHEMA,
                    pg_table=table,
                    source_label=str(path),
                    user_map=user_map,
                    default_user_id=default_user_id,
                    inject_user_id=True,
                    dry_run=dry_run,
                )
            )
        sqlite_conn.commit()
    finally:
        sqlite_conn.close()
    return results


def _import_cache_dbs(base_dir: Path, pg_conn, *, dry_run: bool) -> list[TableImportResult]:
    results: list[TableImportResult] = []
    for filename, table in _CACHE_SOURCES:
        path = base_dir / filename
        if not path.is_file():
            continue
        sqlite_conn = _open_sqlite(path)
        try:
            results.append(
                _copy_sqlite_table(
                    sqlite_conn,
                    pg_conn,
                    sqlite_table=table,
                    pg_schema=_CACHE_SCHEMA,
                    pg_table=table,
                    source_label=str(path),
                    user_map={},
                    default_user_id="",
                    inject_user_id=False,
                    dry_run=dry_run,
                )
            )
        finally:
            sqlite_conn.close()
    return results


def _import_cache_from_app_db(path: Path, pg_conn, *, dry_run: bool) -> list[TableImportResult]:
    """从 zak.db 内嵌 cache 表导入（若存在）。"""
    results: list[TableImportResult] = []
    if not path.is_file():
        return results
    sqlite_conn = _open_sqlite(path)
    try:
        tables = set(_sqlite_tables(sqlite_conn))
        for table in _CACHE_APP_TABLES:
            if table not in tables:
                continue
            results.append(
                _copy_sqlite_table(
                    sqlite_conn,
                    pg_conn,
                    sqlite_table=table,
                    pg_schema=_CACHE_SCHEMA,
                    pg_table=table,
                    source_label=f"{path}#{table}",
                    user_map={},
                    default_user_id="",
                    inject_user_id=False,
                    dry_run=dry_run,
                )
            )
    finally:
        sqlite_conn.close()
    return results


def _archive_paths(paths: Iterable[Path]) -> list[str]:
    existing = [path for path in paths if path.is_file()]
    if not existing:
        return []
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target_dir = BACKUP_DIR / f"sqlite_legacy_{stamp}"
    target_dir.mkdir(parents=True, exist_ok=True)
    archived: list[str] = []
    for path in existing:
        dest = target_dir / path.name
        shutil.move(str(path), str(dest))
        archived.append(str(dest))
    return archived


def import_legacy(options: ImportLegacyOptions | None = None) -> ImportLegacyReport:
    """将本地 SQLite 遗留数据导入 PostgreSQL。"""
    opts = options or ImportLegacyOptions()
    url = require_database_url()

    if opts.upgrade:
        upgrade_head()

    app_path = opts.app_db or get_app_db_path()
    chat_path = opts.chat_db or get_chat_db_path()
    scheduler_json = VNTRADER_DIR / "zak_scheduler.json"

    report = ImportLegacyReport(target_user=opts.username)

    if opts.cache_only:
        if opts.skip_cache:
            raise RuntimeError("--cache-only 与 --skip-cache 不能同时使用")
        with connect_app() as pg_conn:
            report.results.extend(_import_cache_dbs(app_path.parent, pg_conn, dry_run=opts.dry_run))
            report.results.extend(_import_cache_from_app_db(app_path, pg_conn, dry_run=opts.dry_run))
        if opts.archive and not opts.dry_run:
            paths = [app_path.parent / name for name, _ in _CACHE_SOURCES]
            report.archived = _archive_paths(paths)
        return report

    user_map: dict[str, str] = {}
    sqlite_default_id = ""

    with connect_app() as pg_conn:
        if app_path.is_file():
            sqlite_conn = _open_sqlite(app_path)
            try:
                sqlite_default_id = _prepare_app_sqlite(sqlite_conn)
                user_map, users_result = _import_auth_users(sqlite_conn, pg_conn, dry_run=opts.dry_run)
                report.results.append(users_result)
            finally:
                sqlite_conn.close()

        default_user_id = _resolve_target_user_id(
            pg_conn,
            username=opts.username,
            user_map=user_map,
            sqlite_default_id=sqlite_default_id,
        )
        if not user_map and sqlite_default_id:
            user_map[sqlite_default_id] = default_user_id
        if not user_map:
            user_map[default_user_id] = default_user_id

        report.results.extend(
            _import_app_db(
                app_path,
                pg_conn,
                user_map=user_map,
                default_user_id=default_user_id,
                dry_run=opts.dry_run,
            )
        )

        if app_path.is_file():
            sqlite_conn = _open_sqlite(app_path)
            try:
                if "user_preferences" in _sqlite_tables(sqlite_conn):
                    report.results.append(
                        _copy_sqlite_table(
                            sqlite_conn,
                            pg_conn,
                            sqlite_table="user_preferences",
                            pg_schema=_AUTH_SCHEMA,
                            pg_table="user_preferences",
                            source_label=str(app_path),
                            user_map=user_map,
                            default_user_id=default_user_id,
                            inject_user_id=True,
                            dry_run=opts.dry_run,
                        )
                    )
            finally:
                sqlite_conn.close()

        report.results.extend(
            _import_chat_db(
                chat_path,
                pg_conn,
                user_map=user_map,
                default_user_id=default_user_id,
                dry_run=opts.dry_run,
            )
        )
        report.results.append(_import_scheduler_json(pg_conn, scheduler_json=scheduler_json, dry_run=opts.dry_run))

        if not opts.skip_cache:
            report.results.extend(_import_cache_dbs(app_path.parent, pg_conn, dry_run=opts.dry_run))
            report.results.extend(_import_cache_from_app_db(app_path, pg_conn, dry_run=opts.dry_run))

    if opts.archive and not opts.dry_run:
        paths = [app_path, chat_path]
        if not opts.skip_cache:
            paths.extend(app_path.parent / name for name, _ in _CACHE_SOURCES)
        paths.append(scheduler_json)
        report.archived = _archive_paths(paths)

    return report
