"""AgentGateway 事件与请求类型（控制面协议）。"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import Field

from vnpy_llm.domain.base import FrozenModel

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


class AgentEvent(FrozenModel):
    type: AgentEventType = Field(description="事件类型")
    payload: dict[str, Any] = Field(default_factory=dict, description="事件载荷")


class SendRequest(FrozenModel):
    session_id: str = Field(description="会话 ID")
    user_text: str = Field(description="用户输入")
    surface: Surface | None = Field(default=None, description="悬浮球或全屏助手")
    scene: str = Field(default="", description="场景标识")


class SendResult(FrozenModel):
    session_id: str = Field(description="会话 ID")
    turn_id: str = Field(description="轮次 ID")
