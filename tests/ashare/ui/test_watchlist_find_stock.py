"""自选页标的查找（全池 vs 分组筛选）。"""

from __future__ import annotations

import unittest

from vnpy.trader.constant import Exchange

import tests._bootstrap  # noqa: F401
from vnpy_ashare.domain.symbols.stock import StockItem


class WatchlistPoolLookupTests(unittest.TestCase):
    def test_find_stock_item_uses_full_pool_when_group_filtered(self) -> None:
        from vnpy_ashare.ui.quotes.page.quotes_page import QuotesPage

        page = QuotesPage.__new__(QuotesPage)
        full = [
            StockItem(symbol="600000", exchange=Exchange.SSE, name="浦发"),
            StockItem(symbol="000001", exchange=Exchange.SZSE, name="平安"),
        ]
        page.watchlist_pool_stocks = list(full)
        page.all_stocks = [full[0]]
        page.watchlist_pool_items = QuotesPage.watchlist_pool_items.__get__(page, QuotesPage)
        page.find_stock_item = QuotesPage.find_stock_item.__get__(page, QuotesPage)

        found = page.find_stock_item("000001.SZSE")
        self.assertIsNotNone(found)
        assert found is not None
        self.assertEqual(found.symbol, "000001")


if __name__ == "__main__":
    unittest.main()
