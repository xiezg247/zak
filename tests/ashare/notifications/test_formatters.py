"""formatters 测试。"""

from __future__ import annotations

import unittest

from vnpy_ashare.notifications.content.formatters import format_notify_text
from vnpy_ashare.notifications.core.events import (
    NOTIFY_EVENT_MANUAL_TEST,
    NOTIFY_EVENT_SCHEDULER_JOB_FAILED,
    NOTIFY_EVENT_SCREENER_INTRADAY_DONE,
)


class NotifyFormattersTest(unittest.TestCase):
    def test_manual_test_starts_with_zak_prefix(self) -> None:
        text = format_notify_text(NOTIFY_EVENT_MANUAL_TEST, {})
        self.assertTrue(text.startswith("【zak】"))
        self.assertIn("测试消息", text)

    def test_screener_done_includes_title(self) -> None:
        text = format_notify_text(
            NOTIFY_EVENT_SCREENER_INTRADAY_DONE,
            {"message": "intraday_multi 命中 18 条", "hit_count": 18, "recipe": "intraday_multi"},
        )
        self.assertIn("盘中选股完成", text)
        self.assertIn("18", text)

    def test_scheduler_failed_includes_job(self) -> None:
        text = format_notify_text(
            NOTIFY_EVENT_SCHEDULER_JOB_FAILED,
            {"job_id": "screen_intraday", "job_name": "盘中自动选股", "message": "网络错误"},
        )
        self.assertIn("定时任务失败", text)
        self.assertIn("盘中自动选股", text)
        self.assertIn("网络错误", text)
