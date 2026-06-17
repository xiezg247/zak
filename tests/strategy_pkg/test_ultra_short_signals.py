"""极致短线信号与隔日退出测试。"""

from __future__ import annotations

import unittest
from datetime import date

from vnpy_ashare.domain.position_snapshot import PositionRecord
from vnpy_ashare.quotes.core.snapshot import QuoteSnapshot
from vnpy_ashare.trading.exit.overnight_exit import evaluate_overnight_exit
from strategies.signals import build_signal_payload_for_strategy
from strategies.ultra_short_signals import build_limit_board_signal_payload, calc_limit_price


class UltraShortSignalsTest(unittest.TestCase):
    def test_calc_limit_price_main_board(self) -> None:
        self.assertEqual(calc_limit_price(10.0, symbol="600519"), 11.0)

    def test_limit_board_signal_on_limit_up(self) -> None:
        closes = [9.0, 9.5, 10.45]
        highs = [9.2, 9.6, 10.45]
        dates = [date(2026, 6, 15), date(2026, 6, 16), date(2026, 6, 17)]
        payload = build_limit_board_signal_payload(
            closes,
            dates,
            vt_symbol="600519.SSE",
            highs=highs,
        )
        self.assertEqual(payload["signal"], "buy")
        self.assertIsNotNone(payload["ref_buy_price"])

    def test_limit_board_registered_in_signals(self) -> None:
        closes = [9.0, 9.5, 10.45]
        highs = [9.2, 9.6, 10.45]
        dates = [date(2026, 6, 15), date(2026, 6, 16), date(2026, 6, 17)]
        payload = build_signal_payload_for_strategy(
            "AshareLimitBoardStrategy",
            closes,
            dates,
            vt_symbol="600519.SSE",
            fast_window=5,
            slow_window=10,
            highs=highs,
        )
        assert payload is not None
        self.assertEqual(payload["strategy_id"], "AshareLimitBoardStrategy")

    def test_overnight_exit_stop_loss(self) -> None:
        record = PositionRecord(
            symbol="600519",
            exchange="SSE",
            name="茅台",
            cost_price=10.0,
            volume=100,
            buy_date="2026-06-15",
        )
        quote = QuoteSnapshot(
            symbol="600519",
            name="茅台",
            last_price=9.4,
            prev_close=9.5,
            open_price=9.5,
            high_price=9.6,
            low_price=9.3,
            change_amount=-0.1,
            change_pct=-1.05,
            turnover_rate=1.0,
            volume=1000.0,
        )
        result = evaluate_overnight_exit(record, quote=quote, stop_loss_pct=0.05)
        self.assertEqual(result.signal, "sell")
        self.assertTrue(any(hit.rule_id == "stop_loss_pct" for hit in result.rules))


if __name__ == "__main__":
    unittest.main()
