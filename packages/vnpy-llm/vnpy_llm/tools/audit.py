"""LLM 工具调用审计落库（chat.llm_tool_calls）。"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

from vnpy_common.storage.tables.chat import llm_tool_calls as ltc
from vnpy_llm.storage.repository.chat import ChatUserScopedRepository

_PREVIEW_MAX = 800


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _preview(text: str) -> str:
    text = text.strip()
    if len(text) <= _PREVIEW_MAX:
        return text
    return text[:_PREVIEW_MAX] + "…"


class ToolCallRepository(ChatUserScopedRepository):
    table = ltc

    def log_tool_call(
        self,
        *,
        session_id: str,
        tool_name: str,
        arguments: dict[str, Any] | None,
        result: str,
        success: bool = True,
    ) -> None:
        payload = json.dumps(arguments or {}, ensure_ascii=False)
        self.insert_one_for_user(
            id=uuid.uuid4().hex,
            session_id=session_id,
            tool_name=tool_name,
            arguments_json=payload,
            result_preview=_preview(result),
            success=1 if success else 0,
            created_at=_now(),
        )

    def list_recent_tool_calls(self, *, session_id: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit or 50), 200))
        extras = (ltc.c.session_id == session_id,) if session_id else ()
        rows = self.list_for_user(
            ltc.c.id,
            ltc.c.session_id,
            ltc.c.tool_name,
            ltc.c.arguments_json,
            ltc.c.result_preview,
            ltc.c.success,
            ltc.c.created_at,
            extras=extras,
            order_by=(ltc.c.created_at.desc(),),
            limit=limit,
        )
        return [
            {
                "id": row["id"],
                "session_id": row["session_id"],
                "tool_name": row["tool_name"],
                "arguments": json.loads(row["arguments_json"] or "{}"),
                "result_preview": row["result_preview"],
                "success": bool(row["success"]),
                "created_at": row["created_at"],
            }
            for row in rows
        ]


_repo = ToolCallRepository()


def log_tool_call(
    *,
    session_id: str,
    tool_name: str,
    arguments: dict[str, Any] | None,
    result: str,
    success: bool = True,
) -> None:
    _repo.log_tool_call(
        session_id=session_id,
        tool_name=tool_name,
        arguments=arguments,
        result=result,
        success=success,
    )


def list_recent_tool_calls(*, session_id: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    return _repo.list_recent_tool_calls(session_id=session_id, limit=limit)
