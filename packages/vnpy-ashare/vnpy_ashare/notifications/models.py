"""通知领域模型。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NotifyDeliveryResult:
    success: bool
    message: str
    status_code: int | None = None


@dataclass(frozen=True)
class NotifyOutboundMessage:
    text: str
    interactive_card: dict | None = None
