"""通知正文与飞书卡片组装。"""

from vnpy_ashare.notifications.content.delivery import (
    build_notify_outbound,
    interactive_cards_enabled,
)
from vnpy_ashare.notifications.content.feishu_card import (
    build_feishu_interactive_card,
    notify_open_url,
)
from vnpy_ashare.notifications.content.formatters import format_notify_text

__all__ = [
    "build_feishu_interactive_card",
    "build_notify_outbound",
    "format_notify_text",
    "interactive_cards_enabled",
    "notify_open_url",
]
