"""Phase 2 通知测试。"""

from __future__ import annotations

import os
import unittest
from unittest.mock import MagicMock, patch

from vnpy_ashare.notifications.events import (
    NOTIFY_EVENT_EMOTION_STAGE_CHANGE,
    NOTIFY_EVENT_POSITION_ALERT,
    NOTIFY_EVENT_RISK_GATE_CHANGE,
)
from vnpy_ashare.notifications.formatters import format_notify_text
from vnpy_ashare.notifications.prefs import NotifyPrefs
from vnpy_ashare.notifications.service import NotificationService
from vnpy_ashare.quotes.market.emotion_cycle import EmotionCycleTracker
from vnpy_ashare.quotes.market.market_breadth import MarketBreadthSnapshot
from vnpy_ashare.trading.risk.gate import RiskGateEngine


def _breadth(**kwargs) -> MarketBreadthSnapshot:
    defaults = dict(
        up=2000,
        down=2000,
        flat=100,
        limit_up=60,
        limit_down=5,
        total_amount=2e12,
        sample_size=4100,
        updated_at="2026-06-17 10:00",
    )
    defaults.update(kwargs)
    return MarketBreadthSnapshot(**defaults)


class _FakeEngine:
    main_engine = MagicMock()
    event_engine = MagicMock()
    scheduler = MagicMock()
    emotion_cycle_tracker = EmotionCycleTracker()
    risk_gate_engine = RiskGateEngine()


class Phase2NotificationTest(unittest.TestCase):
    def test_emotion_stage_formatter(self) -> None:
        text = format_notify_text(
            NOTIFY_EVENT_EMOTION_STAGE_CHANGE,
            {
                "stage_label": "启动",
                "limit_up_count": 55,
                "limit_down_count": 3,
                "position_pct_max": 0.5,
                "allow_new_positions": True,
            },
        )
        self.assertIn("情绪阶段", text)
        self.assertIn("启动", text)
        self.assertIn("50%", text)

    def test_risk_gate_formatter(self) -> None:
        text = format_notify_text(
            NOTIFY_EVENT_RISK_GATE_CHANGE,
            {
                "state_label": "警戒",
                "warnings": ["当日盈亏 -3.5% 触发警戒阈值"],
                "daily_pnl_pct": -3.5,
            },
        )
        self.assertIn("风控状态", text)
        self.assertIn("警戒", text)

    def test_position_alert_formatter(self) -> None:
        text = format_notify_text(
            NOTIFY_EVENT_POSITION_ALERT,
            {
                "name": "测试股份",
                "symbol": "000001",
                "reasons": "浮亏 · 急跌",
                "pnl_pct": -6.2,
                "exit_signal": "sell",
                "t1_locked": True,
            },
        )
        self.assertIn("持仓提醒", text)
        self.assertIn("测试股份", text)

    @patch.dict(
        os.environ,
        {"NOTIFY_ENABLED": "true", "FEISHU_WEBHOOK_URL": "http://x", "NOTIFY_MIN_INTERVAL_SEC": "0"},
        clear=False,
    )
    @patch("vnpy_ashare.notifications.service.append_notify_delivery_log")
    @patch("vnpy_ashare.notifications.service.FeishuWebhookChannel.send_text")
    @patch("vnpy_ashare.notifications.rules.load_notify_prefs")
    def test_on_market_breadth_stage_change(
        self,
        mock_prefs: MagicMock,
        mock_send: MagicMock,
        mock_log: MagicMock,
    ) -> None:
        mock_prefs.return_value = NotifyPrefs(
            event_subscriptions={NOTIFY_EVENT_EMOTION_STAGE_CHANGE: True},
        )
        mock_send.return_value = type("R", (), {"success": True, "message": "ok", "status_code": 200})()
        engine = _FakeEngine()
        svc = NotificationService(engine, sync=True)
        svc.on_market_breadth(_breadth(limit_up=85))
        mock_send.assert_called_once()
        self.assertIn("情绪阶段", mock_send.call_args.args[0])
        mock_log.assert_called_once()
        svc.on_market_breadth(_breadth(limit_up=85))
        mock_send.assert_called_once()

    @patch.dict(
        os.environ,
        {"NOTIFY_ENABLED": "true", "FEISHU_WEBHOOK_URL": "http://x", "NOTIFY_MIN_INTERVAL_SEC": "0"},
        clear=False,
    )
    @patch("vnpy_ashare.notifications.service.append_notify_delivery_log")
    @patch("vnpy_ashare.notifications.service.FeishuWebhookChannel.send_text")
    @patch("vnpy_ashare.notifications.rules.load_notify_prefs")
    @patch("vnpy_ashare.trading.risk.gate.get_settings")
    def test_evaluate_risk_gate_change(
        self,
        mock_settings: MagicMock,
        mock_prefs: MagicMock,
        mock_send: MagicMock,
        mock_log: MagicMock,
    ) -> None:
        settings = MagicMock()
        settings.value.side_effect = lambda key, default=None: {
            "trading/risk/daily_pnl_pct": "-6",
            "trading/risk/caution_daily_pct": "-3",
            "trading/risk/halt_daily_pct": "-5",
            "trading/risk/caution_float_pct": "-5",
            "trading/risk/manual_halt": 0,
        }.get(key, default)
        mock_settings.return_value = settings
        mock_prefs.return_value = NotifyPrefs(
            event_subscriptions={NOTIFY_EVENT_RISK_GATE_CHANGE: True},
        )
        mock_send.return_value = type("R", (), {"success": True, "message": "ok", "status_code": 200})()
        engine = _FakeEngine()
        svc = NotificationService(engine, sync=True)
        svc.evaluate_risk_gate(avg_float_pnl_pct=-2.0)
        mock_send.assert_called_once()
        self.assertIn("风控状态", mock_send.call_args.args[0])
        mock_log.assert_called_once()
