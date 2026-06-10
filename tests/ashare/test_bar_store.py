"""分 K 本地存储测试。"""

from __future__ import annotations

import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

from vnpy.trader.constant import Exchange, Interval
from vnpy.trader.object import BarData

from vnpy_ashare.data.bar_store import (
    get_scope_overview,
    invalidate_bar_overview_cache,
    iter_bar_overviews,
    load_period_bars,
)


class BarStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        invalidate_bar_overview_cache()

    def tearDown(self) -> None:
        invalidate_bar_overview_cache()

    @patch("vnpy_ashare.data.bar_store.get_database")
    def test_load_period_bars(self, get_database_mock) -> None:
        database = MagicMock()
        get_database_mock.return_value = database
        bars = [
            BarData(
                symbol="600519",
                exchange=Exchange.SSE,
                datetime=datetime(2026, 6, 1, 10, 0),
                interval=Interval.MINUTE,
                open_price=1,
                high_price=1,
                low_price=1,
                close_price=1,
                volume=1,
                gateway_name="DB",
            )
        ]
        database.load_bar_data.return_value = bars

        loaded = load_period_bars(
            "600519",
            Exchange.SSE,
            "1m",
            datetime(2026, 6, 1, 9, 30),
            datetime(2026, 6, 1, 15, 0),
        )
        self.assertEqual(loaded, bars)
        database.load_bar_data.assert_called_once_with(
            "600519",
            Exchange.SSE,
            Interval.MINUTE,
            datetime(2026, 6, 1, 9, 30),
            datetime(2026, 6, 1, 15, 0),
        )

    @patch("vnpy_ashare.data.bar_store.get_database")
    def test_get_scope_overview_uses_configured_database(self, get_database_mock) -> None:
        database = MagicMock()
        get_database_mock.return_value = database
        database.get_bar_overview.return_value = [
            MagicMock(
                symbol="600519",
                exchange=Exchange.SSE,
                interval=Interval.DAILY,
                start=datetime(2020, 1, 2),
                end=datetime(2026, 6, 5),
                count=1280,
            ),
            MagicMock(
                symbol="000001",
                exchange=Exchange.SZSE,
                interval=Interval.DAILY,
                start=datetime(2020, 1, 2),
                end=datetime(2026, 6, 5),
                count=900,
            ),
        ]

        overview = get_scope_overview("600519", Exchange.SSE, "daily")
        self.assertIsNotNone(overview)
        assert overview is not None
        self.assertEqual(overview.symbol, "600519")
        self.assertEqual(overview.count, 1280)
        database.get_bar_overview.assert_called_once()

    @patch("vnpy_ashare.data.bar_store.get_database")
    def test_iter_bar_overviews_filters_by_interval(self, get_database_mock) -> None:
        database = MagicMock()
        get_database_mock.return_value = database
        database.get_bar_overview.return_value = [
            MagicMock(
                symbol="600519",
                exchange=Exchange.SSE,
                interval=Interval.DAILY,
                start=datetime(2020, 1, 2),
                end=datetime(2026, 6, 5),
                count=1280,
            ),
            MagicMock(
                symbol="600519",
                exchange=Exchange.SSE,
                interval=Interval.MINUTE,
                start=datetime(2026, 6, 1, 9, 30),
                end=datetime(2026, 6, 5, 15, 0),
                count=500,
            ),
        ]

        daily_rows = iter_bar_overviews(scope="daily")
        self.assertEqual(len(daily_rows), 1)
        self.assertEqual(daily_rows[0].period, "daily")
        self.assertEqual(daily_rows[0].count, 1280)

    @patch("vnpy_ashare.data.bar_store.get_database")
    def test_overview_cache_reuses_database(self, get_database_mock) -> None:
        database = MagicMock()
        get_database_mock.return_value = database
        database.get_bar_overview.return_value = [
            MagicMock(
                symbol="600519",
                exchange=Exchange.SSE,
                interval=Interval.DAILY,
                start=datetime(2020, 1, 2),
                end=datetime(2026, 6, 5),
                count=1280,
            ),
        ]

        get_scope_overview("600519", Exchange.SSE, "daily")
        get_scope_overview("600519", Exchange.SSE, "daily")
        database.get_bar_overview.assert_called_once()

        invalidate_bar_overview_cache()
        get_scope_overview("600519", Exchange.SSE, "daily")
        self.assertEqual(database.get_bar_overview.call_count, 2)


if __name__ == "__main__":
    unittest.main()
