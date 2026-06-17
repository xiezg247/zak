"""极致短线信号与隔日退出测试。"""

from __future__ import annotations

import unittest
from datetime import date

from strategies.signals import build_signal_payload_for_strategy
from strategies.ultra_short_signals import build_limit_board_signal_payload, calc_limit_price
from vnpy_ashare.domain.trading.position import PositionRecord
from vnpy_ashare.domain.market.quote_snapshot import QuoteSnapshot
from vnpy_ashare.trading.exit.overnight_exit import evaluate_overnight_exit


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

    def test_one_word_board_downgrades_signal(self) -> None:
        closes = [10.0, 10.0, 11.0]
        highs = [10.0, 10.0, 11.0]
        lows = [10.0, 10.0, 11.0]
        dates = [date(2026, 6, 15), date(2026, 6, 16), date(2026, 6, 17)]
        payload = build_limit_board_signal_payload(
            closes,
            dates,
            vt_symbol="600519.SSE",
            highs=highs,
            lows=lows,
            first_time="093500",
        )
        self.assertEqual(payload["signal"], "hold")
        self.assertIn("一字板", " ".join(payload["reasons"]))

    def test_seal_time_boosts_strength(self) -> None:
        closes = [9.0, 9.5, 10.45]
        highs = [9.2, 9.6, 10.45]
        lows = [9.0, 9.4, 10.40]
        dates = [date(2026, 6, 15), date(2026, 6, 16), date(2026, 6, 17)]
        with_seal = build_limit_board_signal_payload(
            closes,
            dates,
            vt_symbol="600519.SSE",
            highs=highs,
            lows=lows,
            first_time="093500",
        )
        without_seal = build_limit_board_signal_payload(
            closes,
            dates,
            vt_symbol="600519.SSE",
            highs=highs,
            lows=lows,
            first_time="",
        )
        self.assertGreater(float(with_seal["strength"] or 0), float(without_seal["strength"] or 0))

    def test_limit_board_strategy_import(self) -> None:
        from strategies.limit_board_strategy import AshareLimitBoardStrategy

        self.assertEqual(AshareLimitBoardStrategy.author, "zak")

    def test_intraday_and_pullback_strategy_import(self) -> None:
        from strategies.intraday_breakout_strategy import AshareIntradayBreakoutStrategy
        from strategies.pullback_strategy import AsharePullbackStrategy

        self.assertEqual(AshareIntradayBreakoutStrategy.author, "zak")
        self.assertEqual(AsharePullbackStrategy.author, "zak")

    def test_classify_intraday_breakout_bar(self) -> None:
        from strategies.ultra_short_signals import classify_intraday_breakout_bar

        closes = [9.0, 9.2, 9.5, 9.8, 10.2]
        highs = [9.1, 9.3, 9.6, 9.9, 10.3]
        vols = [1000.0, 1100.0, 1200.0, 1300.0, 2500.0]
        signal, change = classify_intraday_breakout_bar(
            closes,
            highs,
            vols,
            len(closes) - 1,
            symbol="600519",
            min_change_pct=3.0,
            max_change_pct=7.0,
            volume_ratio_min=1.2,
        )
        self.assertEqual(signal, "buy")
        self.assertGreater(change, 3.0)

    def test_classify_pullback_bar(self) -> None:
        from strategies.ultra_short_signals import classify_pullback_bar

        closes = [10.0, 10.1, 10.0, 9.95, 10.02, 10.01]
        vols = [2000.0, 2100.0, 1900.0, 1800.0, 1500.0, 1200.0]
        signal = classify_pullback_bar(
            closes,
            vols,
            len(closes) - 1,
            ma_window=5,
            pullback_band_pct=2.0,
        )
        self.assertIn(signal, {"buy", "hold"})

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
