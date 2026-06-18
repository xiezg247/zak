"""分 K 开盘止损测试。"""

from __future__ import annotations

import unittest
from datetime import datetime

from vnpy.trader.constant import Exchange, Interval
from vnpy.trader.object import BarData

from vnpy_ashare.domain.time.market_hours import CHINA_TZ
from vnpy_ashare.trading.exit.opening_stop_intraday import detect_opening_stop_from_minute_bars


def _bar(hour: int, minute: int, *, high: float, close: float) -> BarData:
    return BarData(
        symbol="600001",
        exchange=Exchange.SSE,
        datetime=datetime(2026, 6, 18, hour, minute, tzinfo=CHINA_TZ),
        interval=Interval.MINUTE,
        open_price=9.8,
        high_price=high,
        low_price=close - 0.05,
        close_price=close,
        volume=1000.0,
        gateway_name="TEST",
    )


class OpeningStopIntradayTest(unittest.TestCase):
    def test_detect_opening_stop_when_not_recovered(self) -> None:
        bars = [
            _bar(9, 31, high=9.85, close=9.82),
            _bar(9, 45, high=9.92, close=9.88),
            _bar(9, 55, high=9.95, close=9.90),
        ]
        hit, detail = detect_opening_stop_from_minute_bars(
            bars,
            prev_close=10.0,
            open_price=9.8,
            phase="partial",
        )
        self.assertTrue(hit)
        self.assertIn("分 K", detail)

    def test_skip_when_recovered(self) -> None:
        bars = [
            _bar(9, 31, high=9.85, close=9.82),
            _bar(9, 40, high=10.01, close=9.98),
        ]
        hit, _ = detect_opening_stop_from_minute_bars(
            bars,
            prev_close=10.0,
            open_price=9.8,
            phase="partial",
        )
        self.assertFalse(hit)


if __name__ == "__main__":
    unittest.main()
