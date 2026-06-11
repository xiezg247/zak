"""本地 K 线列表与清理测试。"""

from __future__ import annotations

import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

from vnpy.trader.constant import Exchange, Interval

from vnpy_ashare.data.bar_store import delete_scope_bars
from vnpy_ashare.data.bars import cleanup_invalid_daily_bars, load_downloaded_stocks
from vnpy_ashare.domain.models import StockItem
from vnpy_ashare.ui.quotes.table.columns import LOCAL_TABLE_HEADERS, build_local_data_row


class LocalDataRowTests(unittest.TestCase):
    def test_local_headers(self) -> None:
        self.assertEqual(len(LOCAL_TABLE_HEADERS), 8)
        self.assertIn("起始", LOCAL_TABLE_HEADERS)
        self.assertIn("状态", LOCAL_TABLE_HEADERS)

    def test_build_local_data_row(self) -> None:
        item = StockItem(symbol="600519", exchange=Exchange.SSE, name="贵州茅台")
        values = build_local_data_row(
            item,
            "1",
            start="2020-01-02",
            end="2026-06-05",
            count="1280",
            status="✅ 最新",
        )
        self.assertEqual(values[1], "600519")
        self.assertEqual(values[3], "贵州茅台")
        self.assertEqual(values[-1], "✅ 最新")


class CleanupDailyBarsTests(unittest.TestCase):
    @patch("vnpy_ashare.data.bars.get_database")
    def test_cleanup_invalid_overview(self, get_database_mock) -> None:
        database = MagicMock()
        get_database_mock.return_value = database
        valid_exchange = Exchange.SSE
        database.get_bar_overview.return_value = [
            MagicMock(
                interval=Interval.DAILY,
                symbol="600519",
                exchange=valid_exchange,
                start=datetime(2020, 1, 2),
                end=datetime(2026, 6, 5),
                count=100,
            ),
            MagicMock(
                interval=Interval.DAILY,
                symbol="000001",
                exchange=valid_exchange,
                start=None,
                end=datetime(2026, 6, 5),
                count=10,
            ),
        ]

        removed = cleanup_invalid_daily_bars()
        self.assertEqual(removed, [("000001", valid_exchange)])
        database.delete_bar_data.assert_called_once_with(
            "000001",
            valid_exchange,
            Interval.DAILY,
        )

    @patch("vnpy_ashare.data.bars.iter_bar_overviews")
    @patch("vnpy_ashare.data.bars.load_universe_rows")
    def test_load_downloaded_stocks(self, load_universe_rows_mock, iter_mock) -> None:
        from vnpy_ashare.data.bar_store import PeriodBarOverview

        load_universe_rows_mock.return_value = [("600519", Exchange.SSE, "贵州茅台")]
        iter_mock.return_value = [
            PeriodBarOverview(
                symbol="600519",
                exchange=Exchange.SSE,
                period="daily",
                start=datetime(2020, 1, 2),
                end=datetime(2026, 6, 5),
                count=100,
            )
        ]

        items = load_downloaded_stocks()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].name, "贵州茅台")
        iter_mock.assert_called_once_with(scope="daily")

    @patch("vnpy_ashare.data.bars.iter_bar_overviews")
    @patch("vnpy_ashare.data.bars.load_universe_rows")
    def test_load_downloaded_minute_scope(self, load_universe_rows_mock, iter_mock) -> None:
        from vnpy_ashare.data.bar_store import PeriodBarOverview

        load_universe_rows_mock.return_value = []
        iter_mock.return_value = [
            PeriodBarOverview(
                symbol="600519",
                exchange=Exchange.SSE,
                period="1m",
                start=datetime(2026, 1, 2, 10, 0),
                end=datetime(2026, 6, 5, 15, 0),
                count=500,
            )
        ]

        items = load_downloaded_stocks(scope="1m")
        self.assertEqual(len(items), 1)
        iter_mock.assert_called_once_with(scope="1m")


class DeleteScopeBarsTests(unittest.TestCase):
    @patch("vnpy_ashare.data.bar_store.get_database")
    @patch("vnpy_ashare.data.bar_store.get_scope_overview")
    def test_delete_scope_bars(self, overview_mock, get_database_mock) -> None:
        from vnpy_ashare.data.bar_store import PeriodBarOverview

        overview_mock.return_value = PeriodBarOverview(
            symbol="600519",
            exchange=Exchange.SSE,
            period="daily",
            start=datetime(2020, 1, 2),
            end=datetime(2026, 6, 5),
            count=100,
        )
        database = MagicMock()
        get_database_mock.return_value = database

        self.assertTrue(delete_scope_bars("600519", Exchange.SSE, "daily"))
        database.delete_bar_data.assert_called_once_with("600519", Exchange.SSE, Interval.DAILY)

    @patch("vnpy_ashare.data.bar_store.get_scope_overview", return_value=None)
    def test_delete_scope_bars_missing(self, _overview_mock) -> None:
        self.assertFalse(delete_scope_bars("600519", Exchange.SSE, "daily"))


if __name__ == "__main__":
    unittest.main()
