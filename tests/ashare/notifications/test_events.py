"""通知事件常量测试。"""

from __future__ import annotations

import unittest

from vnpy_ashare.notifications.core.events import (
    DEFAULT_EVENT_SUBSCRIPTIONS,
    NOTIFY_EVENT_SCHEDULER_JOB_FAILED,
    NOTIFY_EVENT_SCREENER_INTRADAY_DONE,
)


class NotifyEventsTest(unittest.TestCase):
    def test_default_subscriptions_include_intraday_and_failed(self) -> None:
        self.assertTrue(DEFAULT_EVENT_SUBSCRIPTIONS[NOTIFY_EVENT_SCREENER_INTRADAY_DONE])
        self.assertTrue(DEFAULT_EVENT_SUBSCRIPTIONS[NOTIFY_EVENT_SCHEDULER_JOB_FAILED])
