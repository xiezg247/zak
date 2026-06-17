"""形态选股日 K 加载测试。"""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from vnpy.trader.constant import Exchange, Interval
from vnpy.trader.object import BarData

import tests._bootstrap  # noqa: F401
from vnpy_ashare.data.bar_store import PeriodBarOverview, invalidate_bar_overview_cache
from vnpy_ashare.data.pattern_bars import PATTERN_LOOKBACK_BARS, load_daily_bars_batch, load_daily_bars_tail
from vnpy_ashare.domain.symbols.stock import StockItem


class PatternBarsTests(unittest.TestCase):
    def setUp(self) -> None:
        invalidate_bar_overview_cache()

    def tearDown(self) -> None:
        invalidate_bar_overview_cache()

    @patch("vnpy_ashare.data.pattern_bars.load_scope_bars")
    @patch("vnpy_ashare.data.pattern_bars.get_scope_overview")
    def test_load_daily_bars_tail_limits_window(self, overview_mock: MagicMock, load_mock: MagicMock) -> None:
        end = datetime(2026, 6, 5, 15, 0, 0)
        overview_mock.return_value = PeriodBarOverview(
            symbol="600519",
            exchange=Exchange.SSE,
            period="daily",
            start=datetime(2020, 1, 2),
            end=end,
            count=1280,
        )
        anchor = datetime(2026, 1, 1, 15, 0, 0)
        bars = [
            BarData(
                symbol="600519",
                exchange=Exchange.SSE,
                datetime=anchor + timedelta(days=index),
                interval=Interval.DAILY,
                open_price=100,
                high_price=101,
                low_price=99,
                close_price=100 + index,
                volume=1000,
                gateway_name="DB",
            )
            for index in range(PATTERN_LOOKBACK_BARS + 10)
        ]
        load_mock.return_value = bars

        loaded = load_daily_bars_tail("600519", Exchange.SSE)
        self.assertEqual(len(loaded), PATTERN_LOOKBACK_BARS)
        self.assertEqual(loaded[-1].close_price, bars[-1].close_price)
        load_mock.assert_called_once()
        start_arg = load_mock.call_args.args[3]
        self.assertLess(start_arg, end)

    @patch("vnpy_ashare.data.pattern_bars.load_daily_bars_tail")
    def test_load_daily_bars_batch_deduplicates(self, tail_mock: MagicMock) -> None:
        tail_mock.return_value = []
        items = [
            StockItem(symbol="600519", exchange=Exchange.SSE, name="茅台"),
            StockItem(symbol="600519", exchange=Exchange.SSE, name="茅台"),
        ]
        result = load_daily_bars_batch(items)
        self.assertEqual(len(result), 1)
        tail_mock.assert_called_once()

    @patch("vnpy_ashare.data.pattern_bars.run_parallel_map")
    @patch("vnpy_ashare.data.pattern_bars.load_daily_bars_tail")
    def test_load_daily_bars_batch_uses_parallel_map(self, tail_mock: MagicMock, parallel_mock: MagicMock) -> None:
        tail_mock.return_value = []
        parallel_mock.return_value = [
            (("600519", Exchange.SSE), []),
            (("000001", Exchange.SZSE), []),
        ]
        items = [
            StockItem(symbol="600519", exchange=Exchange.SSE, name="茅台"),
            StockItem(symbol="000001", exchange=Exchange.SZSE, name="平安"),
        ]
        result = load_daily_bars_batch(items, max_workers=2)
        parallel_mock.assert_called_once()
        self.assertEqual(len(result), 2)
        tail_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
