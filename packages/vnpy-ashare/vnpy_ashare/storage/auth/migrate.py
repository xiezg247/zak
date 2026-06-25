"""用户私有表 user_id 列迁移（SQLite）。"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime

from vnpy_common.auth.users import DEFAULT_USERNAME, hash_password
from vnpy_common.storage.sqlite_backend import SqliteBackend

_USERS_SCHEMA_SQLITE = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL DEFAULT '',
    password_hash TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

PRIVATE_TABLES: tuple[str, ...] = (
    "watchlist",
    "watchlist_groups",
    "watchlist_group_members",
    "watchlist_positions",
    "stock_note_memos",
    "stock_note_entries",
    "stock_analysis_reports",
    "trading_plans",
    "trading_plan_symbols",
    "trading_playbook_discipline_daily",
    "screener_schemes",
    "screener_recipes",
    "screener_runs",
    "backtest_runs",
    "feed_subscriptions",
    "feed_cursors",
    "notify_delivery_log",
)

FEED_READS_SCHEMA = """
CREATE TABLE IF NOT EXISTS feed_item_reads (
    user_id TEXT NOT NULL,
    item_id TEXT NOT NULL,
    read_at TEXT NOT NULL,
    PRIMARY KEY (user_id, item_id)
);
"""

USER_PREFS_SCHEMA = """
CREATE TABLE IF NOT EXISTS user_preferences (
    user_id TEXT NOT NULL,
    namespace TEXT NOT NULL,
    key TEXT NOT NULL,
    value_json TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (user_id, namespace, key)
);
"""


def _now_iso() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _ensure_default_user_sqlite(conn: sqlite3.Connection) -> str:
    conn.executescript(_USERS_SCHEMA_SQLITE)
    row = conn.execute("SELECT id FROM users WHERE username = ?", (DEFAULT_USERNAME,)).fetchone()
    if row is not None:
        return str(row[0])
    user_id = uuid.uuid4().hex
    now = _now_iso()
    conn.execute(
        """
        INSERT INTO users (id, username, display_name, password_hash, is_active, created_at, updated_at)
        VALUES (?, ?, ?, ?, 1, ?, ?)
        """,
        (user_id, DEFAULT_USERNAME, "默认用户", hash_password("default"), now, now),
    )
    return user_id


def migrate_user_scope_sqlite(conn: sqlite3.Connection) -> str:
    default_uid = _ensure_default_user_sqlite(conn)
    for table in PRIVATE_TABLES:
        columns = SqliteBackend.table_columns(conn, table)
        if not columns:
            continue
        if "user_id" not in columns:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN user_id TEXT NOT NULL DEFAULT ''")
            conn.execute(f"UPDATE {table} SET user_id = ? WHERE user_id = ''", (default_uid,))
    conn.executescript(FEED_READS_SCHEMA)
    conn.executescript(USER_PREFS_SCHEMA)
    _migrate_feed_reads_from_items(conn, default_uid)
    from vnpy_ashare.storage.auth import users as users_module

    users_module._cached_default_user_id = default_uid
    users_module._cached_default_user_db = "legacy-sqlite-import"
    return default_uid


def _migrate_feed_reads_from_items(conn: sqlite3.Connection, default_uid: str) -> None:
    columns = SqliteBackend.table_columns(conn, "feed_items")
    if not columns or "read_at" not in columns:
        return
    rows = conn.execute(
        "SELECT id, read_at FROM feed_items WHERE read_at IS NOT NULL AND read_at != ''",
    ).fetchall()
    for row in rows:
        conn.execute(
            """
            INSERT OR IGNORE INTO feed_item_reads (user_id, item_id, read_at)
            VALUES (?, ?, ?)
            """,
            (default_uid, row[0], row[1]),
        )
