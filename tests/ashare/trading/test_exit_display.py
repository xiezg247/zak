"""隔日规则展示与 overlay 测试。"""

from __future__ import annotations

import unittest
from unittest import mock

from vnpy_ashare.domain.market.quote_snapshot import QuoteSnapshot
from vnpy_ashare.domain.trading.exit import ExitRuleHit
from vnpy_ashare.domain.trading.position import PositionRecord, PositionSnapshot
from vnpy_ashare.trading.exit.exit_display import (
    exit_rule_cell_color,
    format_exit_rules_summary,
    format_exit_rules_tooltip,
)
from vnpy_ashare.trading.exit.overlay import apply_overnight_exit_overlay


def _snap(**kwargs) -> PositionSnapshot:
    defaults = dict(
        vt_symbol="600000.SSE",
        name="测试",
        cost_price=10.0,
        volume=100,
        buy_date="2026-06-10",
        source="manual",
        last_price=9.4,
        market_value=940.0,
        unrealized_pnl=-60.0,
        unrealized_pnl_pct=-6.0,
        exit_signal="hold",
        signal_snapshot=None,
        t1_locked=False,
        exit_ref_price=None,
        dist_exit_pct=None,
        warnings=(),
        exit_rules=(),
    )
    defaults.update(kwargs)
    return PositionSnapshot(**defaults)  # type: ignore[arg-type]


class ExitDisplayTest(unittest.TestCase):
    def test_format_exit_rules_summary_triggered_first(self) -> None:
        rules = (
            ExitRuleHit(rule_id="a", label="止损", status="triggered", detail="浮亏 -6%"),
            ExitRuleHit(rule_id="b", label="逼近止损", status="near", detail="接近线"),
        )
        self.assertEqual(format_exit_rules_summary(rules), "止损 · 逼近止损?")

    def test_format_exit_rules_tooltip(self) -> None:
        rules = (ExitRuleHit(rule_id="a", label="止损", status="triggered", detail="浮亏 -6%"),)
        tip = format_exit_rules_tooltip(rules)
        self.assertIn("触发", tip)
        self.assertIn("浮亏 -6%", tip)


class ExitRuleCellColorTest(unittest.TestCase):
    def test_triggered_uses_fall_color(self) -> None:
        colors = type("Colors", (), {"fall": "#ff0000"})()
        rules = (ExitRuleHit(rule_id="a", label="止损", status="triggered", detail="浮亏 -6%"),)
        self.assertEqual(exit_rule_cell_color(rules, colors=colors, warning_color="#ffaa00"), "#ff0000")

    def test_near_uses_warning_color(self) -> None:
        colors = type("Colors", (), {"fall": "#ff0000"})()
        rules = (ExitRuleHit(rule_id="b", label="逼近止损", status="near", detail="接近线"),)
        self.assertEqual(exit_rule_cell_color(rules, colors=colors, warning_color="#ffaa00"), "#ffaa00")

    def test_clear_returns_none(self) -> None:
        colors = type("Colors", (), {"fall": "#ff0000"})()
        rules = (ExitRuleHit(rule_id="c", label="封板", status="clear", detail="持有"),)
        self.assertIsNone(exit_rule_cell_color(rules, colors=colors, warning_color="#ffaa00"))


class OvernightExitOverlayRulesTest(unittest.TestCase):
    def test_overlay_attaches_exit_rules(self) -> None:
        record = PositionRecord(
            symbol="600000",
            exchange="SSE",
            name="测试",
            cost_price=10.0,
            volume=100,
            buy_date="2026-06-10",
        )
        with mock.patch(
            "vnpy_ashare.trading.exit.overlay.load_strategy_profile_id",
            return_value="ultra_short",
        ):
            quote = QuoteSnapshot(
                symbol="600000",
                name="测试",
                last_price=9.4,
                prev_close=10.0,
                open_price=9.5,
                high_price=9.6,
                low_price=9.3,
                change_amount=-0.6,
                change_pct=-6.0,
                turnover_rate=1.0,
                volume=1000.0,
                trade_time="2026-06-17 10:30:00",
            )
            merged = apply_overnight_exit_overlay(record, _snap(), quote=quote)
        self.assertTrue(any(hit.rule_id == "stop_loss_pct" for hit in merged.exit_rules))
        self.assertEqual(merged.exit_signal, "sell")


if __name__ == "__main__":
    unittest.main()
