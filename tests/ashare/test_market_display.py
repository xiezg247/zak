"""市场页全量排序与展示切片测试。"""

from __future__ import annotations

import unittest

from vnpy.trader.constant import Exchange

import tests._bootstrap  # noqa: F401
from vnpy_ashare.domain.symbols import StockItem
from vnpy_ashare.domain.market.quote_snapshot import QuoteSnapshot
from vnpy_ashare.ui.quotes.table.display import slice_market_display, sort_market_items


def _quote(symbol: str, *, change_pct: float, amount: float) -> QuoteSnapshot:
    return QuoteSnapshot(
        symbol=symbol,
        name=symbol,
        last_price=10.0,
        prev_close=10.0,
        open_price=10.0,
        high_price=10.0,
        low_price=10.0,
        change_amount=0.0,
        change_pct=change_pct,
        turnover_rate=0.0,
        volume=0,
        amount=amount,
        amplitude=0.0,
        trade_time="",
    )


def _sort_key(column_key: str, item: StockItem, quote: QuoteSnapshot | None, _index_text: str) -> float | str:
    if quote is None:
        return float("-inf")
    if column_key == "change_pct":
        return quote.change_pct
    if column_key == "amount":
        return quote.amount
    return item.symbol


class MarketDisplayTests(unittest.TestCase):
    def test_sort_by_change_pct_desc(self) -> None:
        items = [
            StockItem(symbol="000001", exchange=Exchange.SZSE, name="A"),
            StockItem(symbol="600519", exchange=Exchange.SSE, name="B"),
            StockItem(symbol="300750", exchange=Exchange.SZSE, name="C"),
        ]
        quote_map = {
            "000001.SZ": _quote("000001.SZ", change_pct=1.0, amount=100),
            "600519.SH": _quote("600519.SH", change_pct=5.0, amount=200),
            "300750.SZ": _quote("300750.SZ", change_pct=3.0, amount=300),
        }

        sorted_items = sort_market_items(
            items,
            sort_column="change_pct",
            ascending=False,
            catalog=items,
            quote_map=quote_map,
            sort_key_fn=_sort_key,
        )
        self.assertEqual([item.symbol for item in sorted_items], ["600519", "300750", "000001"])

    def test_live_mode_paginates_sorted_rows(self) -> None:
        items = [StockItem(symbol=f"{idx:06d}", exchange=Exchange.SZSE, name=str(idx)) for idx in range(150)]
        quote_map = {item.tickflow_symbol: _quote(item.tickflow_symbol, change_pct=float(idx), amount=float(idx)) for idx, item in enumerate(items)}
        sorted_items = sort_market_items(
            items,
            sort_column="change_pct",
            ascending=False,
            catalog=items,
            quote_map=quote_map,
            sort_key_fn=_sort_key,
        )
        page0 = slice_market_display(sorted_items, page=0, page_size=100)
        page1 = slice_market_display(sorted_items, page=1, page_size=100)

        self.assertEqual(len(page0), 100)
        self.assertEqual(page0[0].symbol, "000149")
        self.assertEqual(page0[-1].symbol, "000050")
        self.assertEqual(len(page1), 50)
        self.assertEqual(page1[0].symbol, "000049")

    def test_always_paginates_display(self) -> None:
        items = [StockItem(symbol=f"{idx:06d}", exchange=Exchange.SZSE, name=str(idx)) for idx in range(5)]
        display = slice_market_display(items, page=0, page_size=100)
        self.assertEqual(len(display), 5)
        display_page1 = slice_market_display(items, page=1, page_size=3)
        self.assertEqual(len(display_page1), 2)
        self.assertEqual(display_page1[0].symbol, "000003")


if __name__ == "__main__":
    unittest.main()
