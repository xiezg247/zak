"""NotificationService 测试。"""

from __future__ import annotations

import os
import unittest
from unittest.mock import MagicMock, patch

from vnpy_ashare.jobs.core.result import JobResult
from vnpy_ashare.notifications.prefs.store import NotifyPrefs
from vnpy_ashare.notifications.service import NotificationService


class _FakeScheduler:
    def get_job_name(self, job_id: str) -> str:
        return "盘中自动选股"


class _FakeEngine:
    main_engine = MagicMock()
    event_engine = MagicMock()
    scheduler = _FakeScheduler()


class NotificationServiceTest(unittest.TestCase):
    @patch.dict(
        os.environ,
        {"NOTIFY_ENABLED": "true", "FEISHU_WEBHOOK_URL": "http://x", "NOTIFY_MIN_INTERVAL_SEC": "0"},
        clear=False,
    )
    @patch("vnpy_ashare.notifications.service.FeishuWebhookChannel.send_outbound")
    @patch(
        "vnpy_ashare.notifications.rules.engine.load_notify_prefs",
        return_value=type(
            "P",
            (),
            {
                "event_subscriptions": {
                    "screener_intraday_done": True,
                    "screener_post_close_done": False,
                    "scheduler_job_failed": True,
                }
            },
        )(),
    )
    def test_on_job_finished_intraday_success(self, mock_prefs: MagicMock, mock_send: MagicMock) -> None:
        mock_prefs.return_value = NotifyPrefs(
            event_subscriptions={
                "screener_intraday_done": True,
                "screener_post_close_done": False,
                "scheduler_job_failed": True,
            },
        )
        mock_send.return_value = type("R", (), {"success": True, "message": "ok", "status_code": 200})()
        svc = NotificationService(_FakeEngine(), sync=True)
        svc.on_job_finished(
            "screen_intraday",
            JobResult(success=True, message="intraday_multi 命中 18 条", skipped=False),
        )
        mock_send.assert_called_once()
        self.assertIn("【zak】", mock_send.call_args.args[0].text)

    @patch.dict(
        os.environ,
        {"NOTIFY_ENABLED": "true", "FEISHU_WEBHOOK_URL": "http://x", "NOTIFY_MIN_INTERVAL_SEC": "0"},
        clear=False,
    )
    @patch("vnpy_ashare.notifications.service.FeishuWebhookChannel.send_outbound")
    @patch(
        "vnpy_ashare.notifications.rules.engine.load_notify_prefs",
        return_value=type(
            "P",
            (),
            {"event_subscriptions": {"scheduler_job_failed": True, "screener_intraday_done": True}},
        )(),
    )
    def test_on_job_finished_failure(self, mock_prefs: MagicMock, mock_send: MagicMock) -> None:
        mock_prefs.return_value = NotifyPrefs(
            event_subscriptions={
                "scheduler_job_failed": True,
                "screener_intraday_done": True,
            },
        )
        mock_send.return_value = type("R", (), {"success": True, "message": "ok", "status_code": 200})()
        svc = NotificationService(_FakeEngine(), sync=True)
        svc.on_job_finished(
            "screen_intraday",
            JobResult(success=False, message="boom", skipped=False),
        )
        mock_send.assert_called_once()
        self.assertIn("定时任务失败", mock_send.call_args.args[0].text)

    @patch.dict(os.environ, {"NOTIFY_ENABLED": "true", "FEISHU_WEBHOOK_URL": "http://x"}, clear=False)
    @patch("vnpy_ashare.notifications.service.FeishuWebhookChannel.send_outbound")
    def test_skipped_job_does_not_notify(self, mock_send: MagicMock) -> None:
        svc = NotificationService(_FakeEngine(), sync=True)
        svc.on_job_finished("screen_intraday", JobResult(success=True, message="跳过", skipped=True))
        mock_send.assert_not_called()
