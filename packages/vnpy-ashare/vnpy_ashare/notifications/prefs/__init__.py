"""通知 QSettings 偏好。"""

from __future__ import annotations

from dataclasses import dataclass

from vnpy_ashare.config.preferences._settings import coerce_settings_bool, get_settings
from vnpy_ashare.notifications.core.events import DEFAULT_EVENT_SUBSCRIPTIONS

_EVENT_PREFIX = "notify/events/"
_INTERACTIVE_KEY = "notify/use_interactive_card"


@dataclass(frozen=True)
class NotifyPrefs:
    event_subscriptions: dict[str, bool]
    use_interactive_card: bool = True


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
