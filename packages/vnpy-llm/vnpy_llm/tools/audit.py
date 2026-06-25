"""LLM 工具调用审计落库（chat.llm_tool_calls）。"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

from vnpy_ashare.storage.auth.scope import get_user_id
from vnpy_llm.chat.db import tool_calls_connect

_PREVIEW_MAX = 800


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
    uid = get_user_id()
    with tool_calls_connect() as conn:
        conn.execute(
            """
            INSERT INTO llm_tool_calls
            (id, session_id, tool_name, arguments_json, result_preview, success, created_at, user_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                uuid.uuid4().hex,
                session_id,
                tool_name,
                payload,
                _preview(result),
                1 if success else 0,
                _now(),
                uid,
            ),
        )


def list_recent_tool_calls(*, session_id: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    limit = max(1, min(int(limit or 50), 200))
    uid = get_user_id()
    query = """
        SELECT id, session_id, tool_name, arguments_json, result_preview, success, created_at
        FROM llm_tool_calls
        WHERE user_id=?
    """
    params: list[Any] = [uid]
    if session_id:
        query += " AND session_id=?"
        params.append(session_id)
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)

    with tool_calls_connect() as conn:
        rows = conn.execute(query, params).fetchall()

    result: list[dict[str, Any]] = []
    for row in rows:
        result.append(
            {
                "id": row["id"],
                "session_id": row["session_id"],
                "tool_name": row["tool_name"],
                "arguments": json.loads(row["arguments_json"] or "{}"),
                "result_preview": row["result_preview"],
                "success": bool(row["success"]),
                "created_at": row["created_at"],
            }
        )
    return result
