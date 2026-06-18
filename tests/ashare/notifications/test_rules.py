"""NotifyRulesEngine 测试。"""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from vnpy_ashare.notifications.core.events import NOTIFY_EVENT_SCREENER_INTRADAY_DONE
from vnpy_ashare.notifications.rules.engine import NotifyRulesEngine


class NotifyRulesEngineTest(unittest.TestCase):
    def test_disabled_when_notify_off(self) -> None:
        with patch.dict(os.environ, {"NOTIFY_ENABLED": "false", "FEISHU_WEBHOOK_URL": "http://x"}, clear=False):
            engine = NotifyRulesEngine(clock=lambda: 1000.0)
            ok, reason = engine.should_send(NOTIFY_EVENT_SCREENER_INTRADAY_DONE, "k")
            self.assertFalse(ok)
            self.assertIn("开关", reason)

    def test_dedupe_within_window(self) -> None:
        clock = {"t": 1000.0}

        def now() -> float:
            return clock["t"]

        with patch.dict(
            os.environ,
            {"NOTIFY_ENABLED": "true", "FEISHU_WEBHOOK_URL": "http://x", "NOTIFY_MIN_INTERVAL_SEC": "0"},
            clear=False,
        ):
            with patch(
                "vnpy_ashare.notifications.rules.engine.load_notify_prefs",
                return_value=type("P", (), {"event_subscriptions": {NOTIFY_EVENT_SCREENER_INTRADAY_DONE: True}})(),
            ):
                engine = NotifyRulesEngine(clock=now)
                self.assertTrue(engine.should_send(NOTIFY_EVENT_SCREENER_INTRADAY_DONE, "k")[0])
                engine.mark_sent(NOTIFY_EVENT_SCREENER_INTRADAY_DONE, "k")
                clock["t"] = 1100.0
                ok, reason = engine.should_send(NOTIFY_EVENT_SCREENER_INTRADAY_DONE, "k")
                self.assertFalse(ok)
                self.assertIn("去重", reason)
