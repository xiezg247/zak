"""分 K 低吸评估测试。"""

from __future__ import annotations

import unittest
from datetime import datetime

from vnpy.trader.constant import Exchange, Interval
from vnpy.trader.object import BarData

import tests._bootstrap  # noqa: F401
from vnpy_ashare.domain.time.market_hours import CHINA_TZ
from vnpy_ashare.trading.signals.pullback_intraday import evaluate_pullback_intraday


def _bar(
    hour: int,
    minute: int,
    *,
    close: float,
    volume: float = 1000.0,
) -> BarData:
    return BarData(
        symbol="600001",
        exchange=Exchange.SSE,
        datetime=datetime(2026, 6, 18, hour, minute, tzinfo=CHINA_TZ),
        interval=Interval.MINUTE,
        open_price=close,
        high_price=close + 0.02,
        low_price=close - 0.02,
        close_price=close,
        volume=volume,
        gateway_name="TEST",
    )


class PullbackIntradayTest(unittest.TestCase):
    def _session_bars(self) -> list[BarData]:
        bars: list[BarData] = []
        for minute in range(30, 60):
            bars.append(_bar(9, minute, close=10.2, volume=2000.0))
        for minute in range(0, 30):
            bars.append(_bar(10, minute, close=10.15, volume=1800.0))
        for minute in range(30, 60):
            bars.append(_bar(14, minute, close=9.65, volume=600.0))
        bars.append(_bar(14, 35, close=9.62, volume=500.0))
        return bars

    def test_eligible_in_afternoon_dip_zone(self) -> None:
        snapshot = evaluate_pullback_intraday(
            self._session_bars(),
            prev_close=10.0,
            daily_ma5=9.70,
            daily_ma10=9.50,
            min_dip_pct=-5.0,
            max_dip_pct=-3.0,
            phase="closed",
        )
        self.assertTrue(snapshot.eligible)
        self.assertTrue(snapshot.dip_zone)
        self.assertTrue(snapshot.volume_shrink)
        self.assertTrue(snapshot.trigger_time.startswith("143"))

    def test_eligible_near_daily_ma5(self) -> None:
        bars = [
            _bar(9, 35, close=10.0, volume=2000.0),
            _bar(14, 32, close=9.70, volume=800.0),
        ]
        snapshot = evaluate_pullback_intraday(
            bars,
            prev_close=10.0,
            daily_ma5=9.70,
            daily_ma10=9.50,
            phase="closed",
        )
        self.assertTrue(snapshot.eligible)
        self.assertTrue(snapshot.near_ma5)

    def test_reject_before_window(self) -> None:
        bars = [_bar(10, 15, close=9.65, volume=500.0)]
        snapshot = evaluate_pullback_intraday(
            bars,
            prev_close=10.0,
            daily_ma5=9.70,
            daily_ma10=9.50,
            phase="closed",
        )
        self.assertFalse(snapshot.eligible)

    def test_reject_when_trend_broken(self) -> None:
        snapshot = evaluate_pullback_intraday(
            self._session_bars(),
            prev_close=10.0,
            daily_ma5=9.40,
            daily_ma10=9.80,
            phase="closed",
        )
        self.assertFalse(snapshot.eligible)


if __name__ == "__main__":
    unittest.main()
