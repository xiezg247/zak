"""通知渠道抽象。"""

from __future__ import annotations

from typing import Protocol

from vnpy_ashare.notifications.models import NotifyDeliveryResult


class NotifyChannel(Protocol):
    def send_text(self, text: str) -> NotifyDeliveryResult: ...
