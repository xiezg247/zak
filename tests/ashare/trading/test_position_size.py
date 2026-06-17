"""单笔风险计算器测试。"""

from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from vnpy_ashare.config.preferences.trading_risk import TradingRiskPrefs
from vnpy_ashare.trading.risk.position_size import (
    compute_position_size,
    compute_position_size_from_prefs,
    format_position_size_hint,
)


class PositionSizeTest(unittest.TestCase):
    def test_two_percent_rule_example(self) -> None:
        result = compute_position_size(
            total_capital=100_000.0,
            cost_price=10.0,
            stop_loss_pct=0.05,
            per_trade_risk_pct=0.02,
        )
        assert result is not None
        self.assertEqual(result.max_shares, 4000)
        self.assertAlmostEqual(result.max_loss_amount, 2000.0)

    def test_volume_exceeds_suggestion(self) -> None:
        result = compute_position_size(
            total_capital=100_000.0,
            cost_price=10.0,
            stop_loss_pct=0.05,
            per_trade_risk_pct=0.02,
            requested_volume=5000,
        )
        assert result is not None
        self.assertTrue(result.volume_exceeds_suggestion)

    def test_from_prefs_without_capital(self) -> None:
        prefs = TradingRiskPrefs(
            total_capital=None,
            per_trade_risk_pct=0.02,
            stop_loss_pct=0.05,
            daily_pnl_pct=None,
            realized_pnl_today=None,
            caution_daily_pct=-3.0,
            halt_daily_pct=-5.0,
            caution_float_pct=-5.0,
            manual_halt=False,
        )
        with patch(
            "vnpy_ashare.trading.risk.position_size.load_trading_risk_prefs",
            return_value=prefs,
        ):
            self.assertIsNone(compute_position_size_from_prefs(cost_price=10.0))
            self.assertIn("总资金", format_position_size_hint(None))

    def test_trading_skill_compute_position_size(self) -> None:
        from skills.vnpy_trading_skill import VnpyTradingSkill

        prefs = TradingRiskPrefs(
            total_capital=100_000.0,
            per_trade_risk_pct=0.02,
            stop_loss_pct=0.05,
            daily_pnl_pct=None,
            realized_pnl_today=None,
            caution_daily_pct=-3.0,
            halt_daily_pct=-5.0,
            caution_float_pct=-5.0,
            manual_halt=False,
        )
        skill = VnpyTradingSkill()
        skill.setup()
        with patch(
            "vnpy_ashare.config.preferences.trading_risk.load_trading_risk_prefs",
            return_value=prefs,
        ), patch(
            "vnpy_ashare.trading.risk.position_size.load_trading_risk_prefs",
            return_value=prefs,
        ):
            payload = json.loads(skill.compute_position_size(cost_price=10.0))
        self.assertEqual(payload["max_shares"], 4000)


if __name__ == "__main__":
    unittest.main()
