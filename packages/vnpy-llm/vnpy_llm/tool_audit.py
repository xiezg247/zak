"""LLM 工具调用审计落库。"""

from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime
from typing import Any

from vnpy_common.paths import get_app_db_path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS llm_tool_calls (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    arguments_json TEXT NOT NULL DEFAULT '{}',
    result_preview TEXT NOT NULL DEFAULT '',
    success INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_llm_tool_calls_created ON llm_tool_calls(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_llm_tool_calls_session ON llm_tool_calls(session_id);
"""

_PREVIEW_MAX = 800


@contextmanager
def _connect():
    path = get_app_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
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


def _preview(text: str) -> str:
    text = text.strip()
    if len(text) <= _PREVIEW_MAX:
        return text
    return text[:_PREVIEW_MAX] + "…"


def log_tool_call(
    *,
    session_id: str,
    tool_name: str,
    arguments: dict[str, Any] | None,
    result: str,
    success: bool = True,
) -> None:
    payload = json.dumps(arguments or {}, ensure_ascii=False)
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO llm_tool_calls
            (id, session_id, tool_name, arguments_json, result_preview, success, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                uuid.uuid4().hex,
                session_id,
                tool_name,
                payload,
                _preview(result),
                1 if success else 0,
                _now(),
            ),
        )


def list_recent_tool_calls(*, session_id: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    limit = max(1, min(int(limit or 50), 200))
    query = """
        SELECT id, session_id, tool_name, arguments_json, result_preview, success, created_at
        FROM llm_tool_calls
    """
    params: list[Any] = []
    if session_id:
        query += " WHERE session_id=?"
        params.append(session_id)
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)

    with _connect() as conn:
        rows = conn.execute(query, params).fetchall()

    result: list[dict[str, Any]] = []
    for row in rows:
        result.append(
            {
                "id": row[0],
                "session_id": row[1],
                "tool_name": row[2],
                "arguments": json.loads(row[3] or "{}"),
                "result_preview": row[4],
                "success": bool(row[5]),
                "created_at": row[6],
            }
        )
    return result
