"""Tushare 日 K 拉取测试。"""

from __future__ import annotations

import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

import pandas as pd
from vnpy.trader.constant import Exchange, Interval

from vnpy_ashare.integrations.tushare.bars import (
    daily_frame_to_bars,
    download_daily_bars_tushare,
    download_minute_bars_tushare,
    fetch_daily_bars,
    fetch_minute_bars,
    minute_frame_to_bars,
)


class TushareDailyBarsTests(unittest.TestCase):
    def test_daily_frame_to_bars(self) -> None:
        frame = pd.DataFrame(
            [
                {
                    "trade_date": "20250609",
                    "open": 10.0,
                    "high": 10.5,
                    "low": 9.8,
                    "close": 10.2,
                    "vol": 12345,
                    "amount": 9876.5,
                }
            ]
        )
        bars = daily_frame_to_bars(frame, symbol="000550", exchange=Exchange.SZSE)
        self.assertEqual(len(bars), 1)
        bar = bars[0]
        self.assertEqual(bar.symbol, "000550")
        self.assertEqual(bar.exchange, Exchange.SZSE)
        self.assertEqual(bar.interval, Interval.DAILY)
        self.assertEqual(bar.close_price, 10.2)
        self.assertEqual(bar.volume, 12345.0)
        self.assertEqual(bar.turnover, 9876500.0)
        self.assertEqual(bar.gateway_name, "TS")

    def test_fetch_daily_bars_calls_pro_daily(self) -> None:
        frame = pd.DataFrame(
            [
                {
                    "trade_date": "20250609",
                    "open": 1,
                    "high": 1,
                    "low": 1,
                    "close": 1,
                    "vol": 1,
                    "amount": 1,
                }
            ]
        )
        pro = MagicMock()
        pro.daily.return_value = frame
        with patch("vnpy_ashare.integrations.tushare.bars.get_tushare_pro", return_value=pro):
            with patch("vnpy_ashare.integrations.tushare.bars.acquire_tushare"):
                bars = fetch_daily_bars(
                    "000550",
                    Exchange.SZSE,
                    start=datetime(2025, 6, 1),
                    end=datetime(2025, 6, 10),
                )
        self.assertEqual(len(bars), 1)
        pro.daily.assert_called_once()

    def test_download_daily_bars_persists(self) -> None:
        bars = daily_frame_to_bars(
            pd.DataFrame(
                [
                    {
                        "trade_date": "20250609",
                        "open": 1,
                        "high": 1,
                        "low": 1,
                        "close": 1,
                        "vol": 1,
                        "amount": 1,
                    }
                ]
            ),
            symbol="000550",
            exchange=Exchange.SZSE,
        )
        database = MagicMock()
        with patch("vnpy_ashare.integrations.tushare.bars.fetch_daily_bars", return_value=bars):
            with patch("vnpy_ashare.integrations.tushare.bars.get_database", return_value=database):
                with patch("vnpy_ashare.integrations.tushare.bars.invalidate_bar_overview_cache"):
                    count = download_daily_bars_tushare(
                        "000550",
                        Exchange.SZSE,
                        start=datetime(2025, 6, 1),
                        end=datetime(2025, 6, 10),
                    )
        self.assertEqual(count, 1)
        database.save_bar_data.assert_called_once_with(bars)


class TushareMinuteBarsTests(unittest.TestCase):
    def test_minute_frame_to_bars(self) -> None:
        frame = pd.DataFrame(
            [
                {
                    "trade_time": "2025-06-09 09:31:00",
                    "open": 10.0,
                    "high": 10.2,
                    "low": 9.9,
                    "close": 10.1,
                    "vol": 1000,
                    "amount": 10100.0,
                }
            ]
        )
        bars = minute_frame_to_bars(frame, symbol="000550", exchange=Exchange.SZSE)
        self.assertEqual(len(bars), 1)
        self.assertEqual(bars[0].interval, Interval.MINUTE)
        self.assertEqual(bars[0].turnover, 10100.0)

    def test_fetch_minute_bars_chunks(self) -> None:
        frame = pd.DataFrame(
            [
                {
                    "trade_time": "2025-06-09 09:31:00",
                    "open": 1,
                    "high": 1,
                    "low": 1,
                    "close": 1,
                    "vol": 1,
                    "amount": 1,
                }
            ]
        )
        pro = MagicMock()
        pro.stk_mins.return_value = frame
        with patch("vnpy_ashare.integrations.tushare.bars.get_tushare_pro", return_value=pro):
            with patch("vnpy_ashare.integrations.tushare.bars.acquire_tushare"):
                with patch("vnpy_ashare.integrations.tushare.bars.time.sleep"):
                    bars = fetch_minute_bars(
                        "000550",
                        Exchange.SZSE,
                        start=datetime(2025, 6, 1),
                        end=datetime(2025, 7, 15),
                    )
        self.assertEqual(len(bars), 1)
        self.assertGreaterEqual(pro.stk_mins.call_count, 2)

    def test_download_minute_bars_persists(self) -> None:
        bars = minute_frame_to_bars(
            pd.DataFrame(
                [
                    {
                        "trade_time": "2025-06-09 09:31:00",
                        "open": 1,
                        "high": 1,
                        "low": 1,
                        "close": 1,
                        "vol": 1,
                        "amount": 1,
                    }
                ]
            ),
            symbol="000550",
            exchange=Exchange.SZSE,
        )
        database = MagicMock()
        with patch("vnpy_ashare.integrations.tushare.bars.fetch_minute_bars", return_value=bars):
            with patch("vnpy_ashare.integrations.tushare.bars.get_database", return_value=database):
                with patch("vnpy_ashare.integrations.tushare.bars.invalidate_bar_overview_cache"):
                    count = download_minute_bars_tushare(
                        "000550",
                        Exchange.SZSE,
                        start=datetime(2025, 6, 1),
                        end=datetime(2025, 6, 10),
                    )
        self.assertEqual(count, 1)
        database.save_bar_data.assert_called_once_with(bars)


if __name__ == "__main__":
    unittest.main()
