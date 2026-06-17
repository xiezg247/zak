"""对话会话与消息领域模型。"""

from __future__ import annotations

from vnpy_common.domain.base import FrozenModel


class ChatMessage(FrozenModel):
    """单条对话消息。"""

    role: str
    content: str
    created_at: str = ""


class ChatSession(FrozenModel):
    """对话会话元数据（不含消息正文）。"""

    id: str
    title: str
    created_at: str
    updated_at: str
    message_count: int = 0
    scene: str = ""
