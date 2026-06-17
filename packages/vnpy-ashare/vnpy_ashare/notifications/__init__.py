"""出站通知（飞书 Webhook 等）。"""

from vnpy_ashare.notifications.events import (
    DEFAULT_EVENT_SUBSCRIPTIONS,
    NOTIFY_EVENT_MANUAL_TEST,
    NOTIFY_EVENT_SCHEDULER_JOB_FAILED,
    NOTIFY_EVENT_SCREENER_INTRADAY_DONE,
    NOTIFY_EVENT_SCREENER_POST_CLOSE_DONE,
)
from vnpy_ashare.notifications.models import NotifyDeliveryResult
from vnpy_ashare.notifications.service import NotificationService

__all__ = [
    "DEFAULT_EVENT_SUBSCRIPTIONS",
    "NOTIFY_EVENT_MANUAL_TEST",
    "NOTIFY_EVENT_SCHEDULER_JOB_FAILED",
    "NOTIFY_EVENT_SCREENER_INTRADAY_DONE",
    "NOTIFY_EVENT_SCREENER_POST_CLOSE_DONE",
    "NotifyDeliveryResult",
    "NotificationService",
]


def __getattr__(name: str):
    if name == "NotificationService":

        return NotificationService
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
