"""开盘止损与记账盈亏测试。"""

from __future__ import annotations

import unittest
from datetime import date
from unittest.mock import patch

from strategies.signals import build_signal_payload_for_strategy
from vnpy_ashare.domain.market.quote_snapshot import QuoteSnapshot
from vnpy_ashare.domain.trading.position import PositionSnapshot
from vnpy_ashare.quotes.misc.position_anomaly import position_anomaly_reasons
from vnpy_ashare.trading.exit.opening_stop import detect_opening_stop_loss, is_within_opening_minutes
from vnpy_ashare.trading.risk.book_pnl import summarize_book_pnl


def _snap(**kwargs) -> PositionSnapshot:
    defaults = dict(
        vt_symbol="600000.SSE",
        name="测试",
        cost_price=10.0,
        volume=100,
        buy_date="2026-06-10",
        source="manual",
        last_price=9.8,
        market_value=980.0,
        unrealized_pnl=-20.0,
        unrealized_pnl_pct=-2.0,
        exit_signal="hold",
        signal_snapshot=None,
        t1_locked=False,
        exit_ref_price=None,
        dist_exit_pct=None,
        warnings=(),
    )
    defaults.update(kwargs)
    return PositionSnapshot(**defaults)  # type: ignore[arg-type]


class OpeningStopTest(unittest.TestCase):
    def test_within_opening_minutes(self) -> None:
        self.assertTrue(is_within_opening_minutes("2026-06-17 09:45:00"))
        self.assertFalse(is_within_opening_minutes("2026-06-17 10:05:00"))

    def test_opening_stop_loss_detected(self) -> None:
        quote = QuoteSnapshot(
            symbol="600000",
            name="测试",
            last_price=9.7,
            prev_close=10.0,
            open_price=9.8,
            high_price=9.9,
            low_price=9.6,
            change_amount=-0.3,
            change_pct=-3.0,
            turnover_rate=1.0,
            volume=1000.0,
            trade_time="2026-06-17 09:50:00",
        )
        hit, detail = detect_opening_stop_loss(quote)
        self.assertTrue(hit)
        self.assertIn("低开", detail)

    def test_position_anomaly_includes_opening_stop(self) -> None:
        quote = QuoteSnapshot(
            symbol="600000",
            name="测试",
            last_price=9.7,
            prev_close=10.0,
            open_price=9.8,
            high_price=9.9,
            low_price=9.6,
            change_amount=-0.3,
            change_pct=-3.0,
            turnover_rate=1.0,
            volume=1000.0,
            trade_time="2026-06-17 09:50:00",
        )
        reasons = position_anomaly_reasons(snap=_snap(), quote=quote)
        self.assertIn("开盘止损", reasons)

    def test_position_anomaly_opening_stop_prefers_minute_bars(self) -> None:
        quote = QuoteSnapshot(
            symbol="600000",
            name="测试",
            last_price=9.7,
            prev_close=10.0,
            open_price=9.8,
            high_price=9.9,
            low_price=9.6,
            change_amount=-0.3,
            change_pct=-3.0,
            turnover_rate=1.0,
            volume=1000.0,
            trade_time="2026-06-17 09:50:00",
        )
        with patch(
            "vnpy_ashare.quotes.misc.position_anomaly.resolve_opening_stop_for_quote",
            return_value=(True, "低开 -2.0%，30 分钟内未翻红（分 K）"),
        ) as mock_resolve:
            reasons = position_anomaly_reasons(snap=_snap(), quote=quote)
        mock_resolve.assert_called_once()
        self.assertIn("开盘止损", reasons)


class BookPnlTest(unittest.TestCase):
    def test_summarize_book_pnl(self) -> None:
        cache = {"600000.SSE": _snap(unrealized_pnl=-200.0)}
        with (
            patch(
                "vnpy_ashare.trading.risk.book_pnl.load_trading_risk_prefs",
            ) as mock_prefs,
            patch(
                "vnpy_ashare.trading.risk.book_pnl.resolve_realized_pnl_today",
                return_value=-500.0,
            ),
        ):
            from vnpy_ashare.config.preferences.trading_risk import TradingRiskPrefs

            mock_prefs.return_value = TradingRiskPrefs(
                total_capital=100_000.0,
                stop_loss_pct=0.05,
                caution_float_pct=-5.0,
                realized_pnl_today=-500.0,
            )
            summary = summarize_book_pnl(cache)
        self.assertAlmostEqual(summary.total_float_pnl, -200.0)
        self.assertAlmostEqual(summary.combined_pnl_amount, -700.0)


class HalfwayPullbackSignalTest(unittest.TestCase):
    def test_halfway_and_pullback_registered(self) -> None:
        closes = [9.0, 9.2, 9.5, 9.8, 10.2]
        highs = [9.1, 9.3, 9.6, 9.9, 10.3]
        vols = [1000.0, 1100.0, 1200.0, 1300.0, 2500.0]
        dates = [date(2026, 6, 13 + i) for i in range(5)]
        halfway = build_signal_payload_for_strategy(
            "AshareIntradayBreakoutStrategy",
            closes,
            dates,
            vt_symbol="600519.SSE",
            fast_window=5,
            slow_window=10,
            highs=highs,
            volumes=vols,
        )
        assert halfway is not None
        self.assertEqual(halfway["strategy_id"], "AshareIntradayBreakoutStrategy")
        pullback = build_signal_payload_for_strategy(
            "AsharePullbackStrategy",
            closes,
            dates,
            vt_symbol="600519.SSE",
            fast_window=5,
            slow_window=10,
            volumes=vols,
        )
        assert pullback is not None
        self.assertEqual(pullback["strategy_id"], "AsharePullbackStrategy")


if __name__ == "__main__":
    unittest.main()
