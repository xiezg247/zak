"""TickFlow K 线转换测试。"""

from __future__ import annotations

import unittest

import pandas as pd
from vnpy.trader.constant import Exchange, Interval

from vnpy_ashare.data.tickflow_klines import dataframe_to_bars


class TickflowKlinesTests(unittest.TestCase):
    def test_dataframe_to_bars(self) -> None:
        df = pd.DataFrame(
            [
                {
                    "timestamp": 1780623000000,
                    "trade_time": "2026-06-06 09:31:00",
                    "open": 10.0,
                    "high": 10.5,
                    "low": 9.8,
                    "close": 10.2,
                    "volume": 1000,
                    "amount": 10200.0,
                },
                {
                    "timestamp": 1780623060000,
                    "trade_time": "2026-06-06 09:32:00",
                    "open": 10.2,
                    "high": 10.3,
                    "low": 10.1,
                    "close": 10.15,
                    "volume": 800,
                    "amount": 8120.0,
                },
            ]
        )
        bars = dataframe_to_bars(
            df,
            symbol="600519",
            exchange=Exchange.SSE,
            interval=Interval.MINUTE,
        )
        self.assertEqual(len(bars), 2)
        self.assertEqual(bars[0].symbol, "600519")
        self.assertEqual(bars[0].exchange, Exchange.SSE)
        self.assertEqual(bars[0].close_price, 10.2)
        self.assertEqual(bars[0].datetime.strftime("%Y-%m-%d %H:%M:%S"), "2026-06-06 09:31:00")
        self.assertEqual(bars[1].turnover, 8120.0)

    def test_empty_dataframe(self) -> None:
        bars = dataframe_to_bars(
            pd.DataFrame(),
            symbol="000001",
            exchange=Exchange.SZSE,
            interval=Interval.MINUTE,
        )
        self.assertEqual(bars, [])


if __name__ == "__main__":
    unittest.main()
