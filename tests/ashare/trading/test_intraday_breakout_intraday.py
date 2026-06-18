"""分 K 半路评估测试。"""

from __future__ import annotations

import unittest
from datetime import datetime

from vnpy.trader.constant import Exchange, Interval
from vnpy.trader.object import BarData

import tests._bootstrap  # noqa: F401
from vnpy_ashare.domain.time.market_hours import CHINA_TZ
from vnpy_ashare.trading.signals.intraday_breakout_intraday import evaluate_intraday_breakout_intraday


def _bar(
    hour: int,
    minute: int,
    *,
    open_price: float,
    high: float,
    low: float,
    close: float,
    volume: float = 1000.0,
) -> BarData:
    return BarData(
        symbol="600001",
        exchange=Exchange.SSE,
        datetime=datetime(2026, 6, 18, hour, minute, tzinfo=CHINA_TZ),
        interval=Interval.MINUTE,
        open_price=open_price,
        high_price=high,
        low_price=low,
        close_price=close,
        volume=volume,
        gateway_name="TEST",
    )


def _build_session_bars() -> list[BarData]:
    """09:30–09:50 铺垫 + 09:50 半路触发。"""
    bars: list[BarData] = []
    price = 10.0
    for minute in range(30, 50):
        bars.append(
            _bar(
                9,
                minute,
                open_price=price,
                high=price + 0.05,
                low=price - 0.02,
                close=price,
                volume=800.0,
            )
        )
        price += 0.02
    bars.append(
        _bar(
            9,
            50,
            open_price=10.38,
            high=10.55,
            low=10.35,
            close=10.52,
            volume=5000.0,
        )
    )
    for minute in range(51, 55):
        bars.append(
            _bar(
                9,
                minute,
                open_price=10.52,
                high=10.54,
                low=10.48,
                close=10.50,
                volume=1200.0,
            )
        )
    return bars


class IntradayBreakoutIntradayTest(unittest.TestCase):
    def test_eligible_in_morning_window(self) -> None:
        bars = _build_session_bars()
        snapshot = evaluate_intraday_breakout_intraday(
            bars,
            prev_close=10.0,
            symbol="600001",
            volume_ratio_min=1.0,
            phase="closed",
        )
        self.assertTrue(snapshot.eligible)
        self.assertGreaterEqual(snapshot.change_pct, 3.0)
        self.assertLessEqual(snapshot.change_pct, 7.0)
        self.assertTrue(snapshot.trigger_time.startswith("0950"))

    def test_reject_outside_window(self) -> None:
        bars = [
            _bar(10, 35, open_price=10.4, high=10.55, low=10.38, close=10.52, volume=5000.0),
        ]
        snapshot = evaluate_intraday_breakout_intraday(
            bars,
            prev_close=10.0,
            symbol="600001",
            volume_ratio_min=1.0,
            phase="closed",
        )
        self.assertFalse(snapshot.eligible)

    def test_reject_at_limit(self) -> None:
        bars = [
            _bar(9, 45, open_price=10.9, high=11.0, low=10.85, close=11.0, volume=5000.0),
        ]
        snapshot = evaluate_intraday_breakout_intraday(
            bars,
            prev_close=10.0,
            symbol="600001",
            volume_ratio_min=1.0,
            phase="closed",
        )
        self.assertFalse(snapshot.eligible)

    def test_partial_matches_closed_on_full_session(self) -> None:
        bars = _build_session_bars()
        partial = evaluate_intraday_breakout_intraday(
            bars,
            prev_close=10.0,
            symbol="600001",
            volume_ratio_min=1.0,
            phase="partial",
        )
        closed = evaluate_intraday_breakout_intraday(
            bars,
            prev_close=10.0,
            symbol="600001",
            volume_ratio_min=1.0,
            phase="closed",
        )
        self.assertEqual(partial.eligible, closed.eligible)
        self.assertIn("盘中评估", " ".join(partial.warnings))


if __name__ == "__main__":
    unittest.main()
