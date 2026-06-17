"""通知领域模型。"""

from __future__ import annotations

from typing import Any

from pydantic import Field

from vnpy_common.domain.base import FrozenModel, MutableModel


class NotifyDeliveryResult(FrozenModel):
    success: bool = Field(description="投递是否成功")
    message: str = Field(description="结果说明或错误信息")
    status_code: int | None = Field(default=None, description="HTTP 状态码")


class NotifyOutboundMessage(MutableModel):
    text: str = Field(description="纯文本消息正文")
    interactive_card: dict[str, Any] | None = Field(default=None, description="飞书交互卡片 JSON")
