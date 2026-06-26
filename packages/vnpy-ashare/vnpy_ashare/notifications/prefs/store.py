"""通知偏好读写。"""

from __future__ import annotations

from pydantic import Field

from vnpy_ashare.config.preferences._user_pref import load_model_pref, save_model_pref
from vnpy_ashare.notifications.core.events import DEFAULT_EVENT_SUBSCRIPTIONS
from vnpy_common.domain.base import FrozenModel

_PREF_NAMESPACE = "notify"
_PREF_KEY = "prefs"


class NotifyPrefs(FrozenModel):
    event_subscriptions: dict[str, bool] = Field(description="各事件类型的订阅开关")
    use_interactive_card: bool = Field(default=True, description="是否优先发送交互卡片")


def default_notify_prefs() -> NotifyPrefs:
    return NotifyPrefs(
        event_subscriptions=dict(DEFAULT_EVENT_SUBSCRIPTIONS),
        use_interactive_card=True,
    )


def load_notify_prefs() -> NotifyPrefs:
    return load_model_pref(
        _PREF_NAMESPACE,
        _PREF_KEY,
        NotifyPrefs,
        load_default=default_notify_prefs,
    )


def save_event_subscription(event_id: str, enabled: bool) -> None:
    prefs = load_notify_prefs()
    subscriptions = dict(prefs.event_subscriptions)
    subscriptions[event_id] = enabled
    save_model_pref(_PREF_NAMESPACE, _PREF_KEY, NotifyPrefs(event_subscriptions=subscriptions, use_interactive_card=prefs.use_interactive_card))


def save_use_interactive_card(enabled: bool) -> None:
    prefs = load_notify_prefs()
    save_model_pref(
        _PREF_NAMESPACE,
        _PREF_KEY,
        NotifyPrefs(event_subscriptions=prefs.event_subscriptions, use_interactive_card=enabled),
    )
