"""隔日退出 quote 路径规则测试。"""

from __future__ import annotations

import unittest
from unittest import mock

from vnpy_ashare.domain.market.quote_snapshot import QuoteSnapshot
from vnpy_ashare.domain.trading.position import PositionRecord
from vnpy_ashare.trading.exit.overnight_exit import evaluate_overnight_exit


def _record(**kwargs) -> PositionRecord:
    defaults = dict(
        symbol="600000",
        exchange="SSE",
        name="测试",
        cost_price=10.0,
        volume=100,
        buy_date="2026-06-10",
    )
    defaults.update(kwargs)
    return PositionRecord(**defaults)  # type: ignore[arg-type]


def _quote(**kwargs) -> QuoteSnapshot:
    defaults = dict(
        symbol="600000",
        name="测试",
        last_price=9.6,
        prev_close=10.0,
        open_price=9.7,
        high_price=11.0,
        low_price=9.5,
        change_amount=0.6,
        change_pct=10.0,
        turnover_rate=2.0,
        volume=1000.0,
        volume_ratio=1.2,
        trade_time="2026-06-17 10:30:00",
    )
    defaults.update(kwargs)
    return QuoteSnapshot(**defaults)


class OvernightExitQuoteRulesTest(unittest.TestCase):
    def test_gap_down_weak_triggers_sell(self) -> None:
        quote = _quote(last_price=9.5, open_price=9.7, prev_close=10.0, high_price=9.8, change_pct=-5.0)
        with mock.patch(
            "vnpy_ashare.trading.exit.overnight_exit.resolve_opening_stop_for_quote",
            return_value=(False, ""),
        ):
            result = evaluate_overnight_exit(_record(), quote=quote)
        self.assertEqual(result.signal, "sell")
        self.assertTrue(any(hit.rule_id == "gap_down_weak" for hit in result.rules))

    def test_limit_break_triggers_sell(self) -> None:
        quote = _quote(last_price=10.5, high_price=11.0, change_pct=10.0)
        with mock.patch(
            "vnpy_ashare.trading.exit.overnight_exit.resolve_opening_stop_for_quote",
            return_value=(False, ""),
        ):
            with mock.patch(
                "vnpy_ashare.trading.exit.overnight_exit.is_at_limit_board",
                return_value=True,
            ):
                result = evaluate_overnight_exit(_record(), quote=quote)
        self.assertEqual(result.signal, "sell")
        self.assertTrue(any(hit.rule_id == "limit_break" for hit in result.rules))

    def test_limit_hold_when_sealed(self) -> None:
        quote = _quote(last_price=11.0, high_price=11.0, change_pct=10.0)
        with mock.patch(
            "vnpy_ashare.trading.exit.overnight_exit.resolve_opening_stop_for_quote",
            return_value=(False, ""),
        ):
            with mock.patch(
                "vnpy_ashare.trading.exit.overnight_exit.is_at_limit_board",
                return_value=True,
            ):
                result = evaluate_overnight_exit(_record(), quote=quote)
        self.assertTrue(any(hit.rule_id == "limit_hold" for hit in result.rules))
        self.assertFalse(any(hit.rule_id == "limit_break" for hit in result.rules))


if __name__ == "__main__":
    unittest.main()
