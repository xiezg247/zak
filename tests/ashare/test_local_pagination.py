"""本地页分页加载测试。"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from vnpy.trader.constant import Exchange

from vnpy_ashare.domain.symbols import StockItem
from vnpy_ashare.ui.quotes.controllers.pagination import MarketPaginationController
from vnpy_ashare.ui.quotes.page.config import LOCAL_PAGE_SIZE, PAGE_CONFIGS


class TestLocalPagination(unittest.TestCase):
    def test_local_page_config(self) -> None:
        local = PAGE_CONFIGS["本地"]
        self.assertTrue(local.use_local_pagination)
        self.assertEqual(local.local_page_size, LOCAL_PAGE_SIZE)

    def test_page_count_for_local(self) -> None:
        page = MagicMock()
        page.config = PAGE_CONFIGS["本地"]
        page._local_total = 120
        page._market_page = 0
        page._market_total = 0
        page.market_auto_refresh_enabled = MagicMock(return_value=False)
        controller = MarketPaginationController(page)
        self.assertEqual(controller.page_count(), 3)
        self.assertTrue(controller.should_show_pagination())

    def test_load_downloaded_stocks_page_slice(self) -> None:
        from unittest.mock import patch

        from vnpy_ashare.data import bars as bars_module

        rows = [
            MagicMock(symbol=f"{idx:06d}", exchange=Exchange.SSE, period="daily", start=None, end=None, count=10)
            for idx in range(1, 6)
        ]
        with patch("vnpy_ashare.data.bars.iter_bar_overviews", return_value=rows):
            with patch("vnpy_ashare.data.bars.load_universe_rows", return_value=[]):
                page_items = bars_module.load_downloaded_stocks_page(scope="daily", offset=1, limit=2)
                total = bars_module.count_downloaded_stocks(scope="daily")
        self.assertEqual(len(page_items), 2)
        self.assertEqual(page_items[0].symbol, "000002")
        self.assertEqual(total, 5)


if __name__ == "__main__":
    unittest.main()
