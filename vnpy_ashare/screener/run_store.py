"""选股运行历史落库。"""

from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from vnpy_ashare.paths import APP_DB_PATH

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
    APP_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(APP_DB_PATH)
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
    runs = list_runs(limit=1)
    return runs[0] if runs else None


def delete_run(run_id: str) -> bool:
    with _connect() as conn:
        cursor = conn.execute("DELETE FROM screener_runs WHERE id=?", (run_id,))
        return cursor.rowcount > 0


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
