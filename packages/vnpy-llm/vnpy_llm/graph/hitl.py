"""Human-in-the-loop：选股/配方草案 pending_confirm 检测。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Literal

from vnpy_llm.chat.client import LlmClientError

DraftKind = Literal["screener", "recipe"]

_PROPOSE_TOOLS: dict[str, DraftKind] = {
    "propose_screening": "screener",
    "propose_recipe": "recipe",
}

HITL_HINTS: dict[DraftKind, str] = {
    "screener": "已生成选股方案草案，请在弹窗中确认后执行。",
    "recipe": "已生成多因子配方草案，请在弹窗中确认后执行。",
}


@dataclass(frozen=True)
class DraftPendingInfo:
    draft_id: str
    draft_kind: DraftKind
    summary: str = ""
    message: str = ""


class DraftPendingStop(LlmClientError):
    """工具返回 pending_confirm，图编排暂停等待 UI 确认。"""

    def __init__(self, info: DraftPendingInfo) -> None:
        self.info = info
        super().__init__(info.message or HITL_HINTS[info.draft_kind])


def parse_draft_pending(tool_name: str, result: str) -> DraftPendingInfo | None:
    """从 propose_* 工具 JSON 结果解析待确认草案。"""
    draft_kind = _PROPOSE_TOOLS.get(tool_name)
    if draft_kind is None:
        return None
    try:
        payload = json.loads(result or "")
    except json.JSONDecodeError:
        return None
    if payload.get("status") != "pending_confirm":
        return None
    draft_id = payload.get("draft_id")
    if not isinstance(draft_id, str) or not draft_id.strip():
        return None
    summary = str(payload.get("summary", "") or "")
    message = str(payload.get("message", "") or "")
    return DraftPendingInfo(
        draft_id=draft_id.strip(),
        draft_kind=draft_kind,
        summary=summary,
        message=message,
    )
