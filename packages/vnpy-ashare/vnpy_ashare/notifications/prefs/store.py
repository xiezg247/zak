"""通知 QSettings 偏好读写。"""

from __future__ import annotations

from pydantic import Field

from vnpy_ashare.config.preferences._settings import coerce_settings_bool, get_settings
from vnpy_ashare.notifications.core.events import DEFAULT_EVENT_SUBSCRIPTIONS
from vnpy_common.domain.base import FrozenModel

_EVENT_PREFIX = "notify/events/"
_INTERACTIVE_KEY = "notify/use_interactive_card"


class NotifyPrefs(FrozenModel):
    event_subscriptions: dict[str, bool] = Field(description="各事件类型的订阅开关")
    use_interactive_card: bool = Field(default=True, description="是否优先发送交互卡片")


def load_notify_prefs() -> NotifyPrefs:
    settings = get_settings()
    subscriptions: dict[str, bool] = {}
    for event_id, default in DEFAULT_EVENT_SUBSCRIPTIONS.items():
        key = f"{_EVENT_PREFIX}{event_id}"
        subscriptions[event_id] = coerce_settings_bool(settings.value(key), default=default)
    use_interactive = coerce_settings_bool(settings.value(_INTERACTIVE_KEY), default=True)
    return NotifyPrefs(event_subscriptions=subscriptions, use_interactive_card=use_interactive)


def save_event_subscription(event_id: str, enabled: bool) -> None:
    settings = get_settings()
    settings.setValue(f"{_EVENT_PREFIX}{event_id}", enabled)
    settings.sync()


def save_use_interactive_card(enabled: bool) -> None:
    settings = get_settings()
    settings.setValue(_INTERACTIVE_KEY, enabled)
    settings.sync()
