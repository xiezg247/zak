"""通知出站消息组装。"""

from __future__ import annotations

import os
from typing import Any

from vnpy_ashare.config.preferences._settings import coerce_settings_bool, get_settings
from vnpy_ashare.notifications.content.feishu_card import build_feishu_interactive_card
from vnpy_ashare.notifications.content.formatters import format_notify_text
from vnpy_ashare.notifications.core.models import NotifyOutboundMessage


def interactive_cards_enabled() -> bool:
    raw = os.environ.get("NOTIFY_FEISHU_INTERACTIVE", "").strip()
    if raw.lower() in {"0", "false", "no", "off"}:
        return False
    if raw.lower() in {"1", "true", "yes", "on"}:
        return True
    settings = get_settings()
    return coerce_settings_bool(settings.value("notify/use_interactive_card"), default=True)


def build_notify_outbound(event_id: str, payload: dict[str, Any]) -> NotifyOutboundMessage:
    text = format_notify_text(event_id, payload)
    card = build_feishu_interactive_card(event_id, payload) if interactive_cards_enabled() else None
    return NotifyOutboundMessage(text=text, interactive_card=card)
