"""AgentGateway 事件与请求类型（控制面协议）。"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal

Surface = Literal["floating", "assistant"]


class AgentEventType(str, Enum):
    CHAT_DELTA = "chat.delta"
    CHAT_STARTED = "chat.started"
    CHAT_FINISHED = "chat.finished"
    CHAT_CANCELLED = "chat.cancelled"
    CHAT_FAILED = "chat.failed"
    CONTEXT_CHANGED = "context.changed"
    TOOLS_STATUS = "tools.status"
    TOOL_STARTED = "tool.started"
    TOOL_FINISHED = "tool.finished"
    TRACE_CHANGED = "trace.changed"
    SESSION_CHANGED = "session.changed"


@dataclass(frozen=True)
class AgentEvent:
    type: AgentEventType
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SendRequest:
    session_id: str
    user_text: str
    surface: Surface | None = None
    scene: str = ""


@dataclass(frozen=True)
class SendResult:
    session_id: str
    turn_id: str
