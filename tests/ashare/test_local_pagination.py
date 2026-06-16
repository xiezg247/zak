"""本地页分页加载与全库搜索测试。"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from vnpy.trader.constant import Exchange

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
        page.search_edit = MagicMock()
        page.search_edit.text.return_value = ""
        page.market_auto_refresh_enabled = MagicMock(return_value=False)
        controller = MarketPaginationController(page)
        self.assertEqual(controller.page_count(), 3)
        self.assertTrue(controller.should_show_pagination())

    def test_pagination_visible_when_total_below_page_size(self) -> None:
        page = MagicMock()
        page.config = PAGE_CONFIGS["本地"]
        page._local_total = 12
        page.search_edit = MagicMock()
        page.search_edit.text.return_value = ""
        controller = MarketPaginationController(page)
        self.assertTrue(controller.should_show_pagination())
        self.assertEqual(controller.page_count(), 1)

    def test_load_downloaded_stocks_page_slice(self) -> None:
        from vnpy_ashare.data import bars as bars_module

        rows = [MagicMock(symbol=f"{idx:06d}", exchange=Exchange.SSE, period="daily", start=None, end=None, count=10) for idx in range(1, 6)]
        with patch("vnpy_ashare.data.bars.iter_bar_overviews", return_value=rows):
            with patch("vnpy_ashare.data.bars.load_universe_names_for_keys", return_value={}):
                page_items = bars_module.load_downloaded_stocks_page(scope="daily", offset=1, limit=2)
                total = bars_module.count_downloaded_stocks(scope="daily")
        self.assertEqual(len(page_items), 2)
        self.assertEqual(page_items[0].symbol, "000002")
        self.assertEqual(total, 5)

    def test_search_downloaded_stocks_page(self) -> None:
        from vnpy_ashare.data import bars as bars_module

        rows = [MagicMock(symbol=f"{idx:06d}", exchange=Exchange.SSE) for idx in range(1, 6)]
        name_map = {
            ("000001", Exchange.SSE): "平安银行",
            ("000002", Exchange.SSE): "万科A",
            ("000003", Exchange.SSE): "万科B",
            ("000004", Exchange.SSE): "国华网安",
            ("000005", Exchange.SSE): "世纪星源",
        }
        with patch("vnpy_ashare.data.bars.iter_bar_overviews", return_value=rows):
            with patch("vnpy_ashare.data.bars.load_universe_names_for_keys", return_value=name_map):
                items, total = bars_module.search_downloaded_stocks_page(
                    scope="daily",
                    keyword="万科",
                    offset=0,
                    limit=10,
                )
        self.assertEqual(total, 2)
        self.assertEqual([item.symbol for item in items], ["000002", "000003"])

    def test_search_downloaded_stocks_paginates(self) -> None:
        from vnpy_ashare.data import bars as bars_module

        rows = [MagicMock(symbol=f"{idx:06d}", exchange=Exchange.SSE) for idx in range(1, 11)]
        with patch("vnpy_ashare.data.bars.iter_bar_overviews", return_value=rows):
            with patch("vnpy_ashare.data.bars.load_universe_names_for_keys", return_value={}):
                page0, total = bars_module.search_downloaded_stocks_page(
                    scope="daily",
                    keyword="000",
                    offset=0,
                    limit=3,
                )
                page1, _ = bars_module.search_downloaded_stocks_page(
                    scope="daily",
                    keyword="000",
                    offset=3,
                    limit=3,
                )
        self.assertEqual(total, 10)
        self.assertEqual(len(page0), 3)
        self.assertEqual(page0[0].symbol, "000001")
        self.assertEqual(len(page1), 3)
        self.assertEqual(page1[0].symbol, "000004")


if __name__ == "__main__":
    unittest.main()
