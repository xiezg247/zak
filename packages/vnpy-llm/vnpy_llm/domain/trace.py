"""Trace 调用链路领域模型。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from vnpy_common.ai.protocol import AiChartSpec
from vnpy_common.domain.base import MutableModel
from vnpy_common.domain.serialize import dump_json

TraceKind = Literal["routing", "tool", "reply", "error", "handoff", "team"]
TraceStatus = Literal["running", "ok", "error"]
TurnStatus = Literal["running", "ok", "error"]


class TraceStep(MutableModel):
    """单步 Trace（路由 / 工具 / 回复 / 错误）。"""

    id: str
    turn_id: str
    kind: TraceKind
    name: str
    status: TraceStatus
    summary: str
    detail: dict[str, Any] = Field(default_factory=dict)
    started_at: float = 0.0
    duration_ms: int | None = None

    def persist_dict(self) -> dict[str, Any]:
        """持久化 dict（不含运行时 started_at）。"""
        return dump_json(self, exclude={"started_at"})


class TurnTrace(MutableModel):
    """一轮用户提问的完整 Trace（含多个 Step）。"""

    turn_id: str
    session_id: str
    user_text: str
    status: TurnStatus = "running"
    steps: list[TraceStep] = Field(default_factory=list)
    attachments: list[AiChartSpec] = Field(default_factory=list, description="聊天内嵌迷你图")
    started_at: float = 0.0
    created_at: str = ""

    def persist_dict(self) -> dict[str, Any]:
        """持久化 dict（不含运行时 started_at）。"""
        return {
            "turn_id": self.turn_id,
            "session_id": self.session_id,
            "user_text": self.user_text,
            "status": self.status,
            "created_at": self.created_at,
            "steps": [step.persist_dict() for step in self.steps],
            "attachments": [item.model_dump() for item in self.attachments],
        }

    @classmethod
    def from_persist_dict(cls, data: dict[str, Any]) -> TurnTrace:
        """dict → TurnTrace（兼容历史 JSON 缺省字段）。"""
        payload = dict(data)
        if "status" not in payload:
            payload["status"] = "ok"
        payload["steps"] = [TraceStep.model_validate(item) for item in (payload.get("steps") or [])]
        raw_attachments = payload.pop("attachments", None) or []
        payload["attachments"] = [AiChartSpec.model_validate(item) for item in raw_attachments]
        return cls.model_validate(payload)
