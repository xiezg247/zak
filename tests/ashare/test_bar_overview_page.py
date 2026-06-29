"""dbbaroverview 分页查询测试。"""

from __future__ import annotations

import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

from vnpy.trader.constant import Exchange

from vnpy_ashare.data.bars import (
    count_downloaded_stocks,
    load_downloaded_stocks_page,
    search_downloaded_stocks_page,
)
from vnpy_ashare.domain.data.bar import PeriodBarOverview
from vnpy_ashare.storage.repositories.bar_overview import BarOverviewRepository


class BarOverviewRepositoryTests(unittest.TestCase):
    @patch.object(BarOverviewRepository, "run")
    def test_page_scope_returns_overviews(self, run_mock: MagicMock) -> None:
        run_mock.return_value = [
            {
                "symbol": "600519",
                "exchange": "SSE",
                "count": 100,
                "start": datetime(2020, 1, 2),
                "end": datetime(2026, 6, 5),
            }
        ]
        repo = BarOverviewRepository()
        rows = repo.page_scope("daily", offset=50, limit=50)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].symbol, "600519")
        self.assertEqual(rows[0].period, "daily")
        run_mock.assert_called_once()

    @patch("vnpy_ashare.data.bars.page_scope_bar_overviews")
    @patch("vnpy_ashare.data.bars.load_universe_names_for_keys")
    def test_load_downloaded_stocks_page_only_fetches_one_page(
        self,
        names_mock: MagicMock,
        page_mock: MagicMock,
    ) -> None:
        page_mock.return_value = [
            PeriodBarOverview(
                symbol="600519",
                exchange=Exchange.SSE,
                period="daily",
                start=datetime(2020, 1, 2),
                end=datetime(2026, 6, 5),
                count=100,
            )
        ]
        names_mock.return_value = {("600519", Exchange.SSE): "贵州茅台"}

        items = load_downloaded_stocks_page(scope="daily", offset=50, limit=50)
        page_mock.assert_called_once_with("daily", offset=50, limit=50)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].name, "贵州茅台")

    @patch("vnpy_ashare.data.bars.count_scope_bar_overviews")
    def test_count_downloaded_stocks_uses_db_count(self, count_mock: MagicMock) -> None:
        count_mock.return_value = 3210
        self.assertEqual(count_downloaded_stocks(scope="daily"), 3210)
        count_mock.assert_called_once_with("daily")

    @patch("vnpy_ashare.data.bars.search_scope_bar_overviews_page")
    @patch("vnpy_ashare.data.bars.load_universe_names_for_keys")
    def test_search_downloaded_stocks_page_delegates_to_db(
        self,
        names_mock: MagicMock,
        search_mock: MagicMock,
    ) -> None:
        search_mock.return_value = (
            [
                PeriodBarOverview(
                    symbol="000001",
                    exchange=Exchange.SZSE,
                    period="daily",
                    start=datetime(2020, 1, 2),
                    end=datetime(2026, 6, 5),
                    count=80,
                )
            ],
            1,
        )
        names_mock.return_value = {("000001", Exchange.SZSE): "平安银行"}

        items, total = search_downloaded_stocks_page(
            scope="daily",
            keyword="平安",
            offset=0,
            limit=50,
        )
        search_mock.assert_called_once_with("daily", "平安", offset=0, limit=50)
        self.assertEqual(total, 1)
        self.assertEqual(items[0].symbol, "000001")


if __name__ == "__main__":
    unittest.main()
