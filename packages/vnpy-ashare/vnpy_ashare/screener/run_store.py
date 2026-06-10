"""选股运行历史落库（SQLite app_db）。

UI 经 ScreeningService 访问，禁止页面直连。``config`` 含 trigger / recipe_id / read_at 等元数据。
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from vnpy_common.paths import get_app_db_path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS screener_runs (
    id TEXT PRIMARY KEY,
    condition TEXT NOT NULL,
    source TEXT NOT NULL,
    row_count INTEGER NOT NULL,
    total_scanned INTEGER NOT NULL DEFAULT 0,
    config_json TEXT NOT NULL DEFAULT '{}',
    result_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_screener_runs_created ON screener_runs(created_at DESC);
"""


@dataclass
class ScreenerRunRecord:
    """单次选股运行记录。"""

    id: str
    condition: str
    source: str
    row_count: int
    total_scanned: int
    config: dict[str, Any]
    rows: list[dict[str, Any]]
    created_at: str


@contextmanager
def _connect():
    path = get_app_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(_SCHEMA)
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def save_run(
    *,
    condition: str,
    source: str,
    rows: list[dict[str, Any]],
    total_scanned: int = 0,
    config: dict[str, Any] | None = None,
) -> ScreenerRunRecord:
    """持久化选股结果并返回完整记录。"""
    run_id = uuid.uuid4().hex
    now = _now()
    payload = json.dumps(rows, ensure_ascii=False)
    config_payload = json.dumps(config or {}, ensure_ascii=False)
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO screener_runs
            (id, condition, source, row_count, total_scanned, config_json, result_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                condition,
                source,
                len(rows),
                total_scanned,
                config_payload,
                payload,
                now,
            ),
        )
    return ScreenerRunRecord(
        id=run_id,
        condition=condition,
        source=source,
        row_count=len(rows),
        total_scanned=total_scanned,
        config=config or {},
        rows=list(rows),
        created_at=now,
    )


def list_runs(*, limit: int = 20) -> list[ScreenerRunRecord]:
    """按创建时间倒序列出历史运行。"""
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT id, condition, source, row_count, total_scanned, config_json, result_json, created_at
            FROM screener_runs
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [_row_to_record(row) for row in rows]


def get_run(run_id: str) -> ScreenerRunRecord | None:
    """按 id 读取单次运行。"""
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT id, condition, source, row_count, total_scanned, config_json, result_json, created_at
            FROM screener_runs WHERE id=?
            """,
            (run_id,),
        ).fetchone()
    if row is None:
        return None
    return _row_to_record(row)


def get_latest_run() -> ScreenerRunRecord | None:
    """最近一条运行记录。"""
    runs = list_runs(limit=1)
    return runs[0] if runs else None


def find_previous_run_by_recipe(
    recipe_id: str,
    *,
    exclude_run_id: str = "",
) -> ScreenerRunRecord | None:
    """查找同配方的上一次运行（按 created_at 倒序，跳过 exclude_run_id）。"""
    rid = recipe_id.strip()
    if not rid:
        return None
    for record in list_runs(limit=50):
        if exclude_run_id and record.id == exclude_run_id:
            continue
        if str(record.config.get("recipe_id", "")) == rid:
            return record
    return None


def delete_run(run_id: str) -> bool:
    """删除运行记录；成功返回 True。"""
    with _connect() as conn:
        cursor = conn.execute("DELETE FROM screener_runs WHERE id=?", (run_id,))
        return cursor.rowcount > 0


def update_run_config(run_id: str, config: dict[str, Any]) -> bool:
    """更新运行的 config_json（如标记 read_at）。"""
    payload = json.dumps(config, ensure_ascii=False)
    with _connect() as conn:
        cursor = conn.execute(
            "UPDATE screener_runs SET config_json=? WHERE id=?",
            (payload, run_id),
        )
        return cursor.rowcount > 0


def mark_run_read(run_id: str) -> bool:
    """定时选股结果标记已读（写入 config.read_at）。"""
    record = get_run(run_id)
    if record is None:
        return False
    config = dict(record.config)
    if config.get("read_at"):
        return True
    config["read_at"] = _now()
    return update_run_config(run_id, config)


def is_auto_run(config: dict[str, Any]) -> bool:
    """是否为自动选股（定时 / AI / 配方）运行。"""
    trigger = str(config.get("trigger", ""))
    if trigger.startswith("scheduled_") or trigger.startswith("ai_"):
        return True
    if config.get("recipe_id"):
        return True
    return False


def is_strategy_run(config: dict[str, Any]) -> bool:
    """是否为策略选股页手动运行（非自动）。"""
    return not is_auto_run(config)


def is_run_unread(config: dict[str, Any]) -> bool:
    """定时运行且尚未标记 read_at。"""
    trigger = str(config.get("trigger", ""))
    return trigger.startswith("scheduled_") and not config.get("read_at")


def _row_to_record(row: sqlite3.Row) -> ScreenerRunRecord:
    return ScreenerRunRecord(
        id=str(row["id"]),
        condition=str(row["condition"]),
        source=str(row["source"]),
        row_count=int(row["row_count"]),
        total_scanned=int(row["total_scanned"]),
        config=json.loads(str(row["config_json"] or "{}")),
        rows=json.loads(str(row["result_json"] or "[]")),
        created_at=str(row["created_at"]),
    )
