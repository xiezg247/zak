"""domain.symbols 符号互转测试。"""

from __future__ import annotations

import unittest

from vnpy.trader.constant import Exchange

from vnpy_ashare.domain.symbols.stock import (
    StockItem,
    parse_stock_symbol,
    symbol_exchange_to_tickflow,
    symbol_exchange_to_ts_code,
    ts_code_to_vt_symbol,
    vt_symbol_to_symbol,
    vt_symbol_to_ts_code,
)


class SymbolConversionTests(unittest.TestCase):
    def test_ts_code_roundtrip(self) -> None:
        self.assertEqual(ts_code_to_vt_symbol("600519.SH"), "600519.SSE")
        self.assertEqual(vt_symbol_to_ts_code("600519.SSE"), "600519.SH")

    def test_symbol_exchange_to_ts_code(self) -> None:
        self.assertEqual(symbol_exchange_to_ts_code("000001", Exchange.SZSE), "000001.SZ")
        self.assertEqual(symbol_exchange_to_ts_code("600519", Exchange.SSE), "600519.SH")

    def test_stock_item_ts_code_property(self) -> None:
        item = StockItem(symbol="600519", exchange=Exchange.SSE, name="贵州茅台")
        self.assertEqual(item.ts_code, "600519.SH")
        self.assertEqual(item.tickflow_symbol, "600519.SH")

    def test_symbol_exchange_to_tickflow(self) -> None:
        self.assertEqual(symbol_exchange_to_tickflow("600519", Exchange.SSE), "600519.SH")

    def test_parse_stock_symbol_formats(self) -> None:
        item = parse_stock_symbol("600519.SSE")
        assert item is not None
        self.assertEqual(item.symbol, "600519")
        self.assertEqual(item.exchange, Exchange.SSE)

        tf_item = parse_stock_symbol("000001.SZ")
        assert tf_item is not None
        self.assertEqual(tf_item.exchange, Exchange.SZSE)

        bare = parse_stock_symbol("600519")
        assert bare is not None
        self.assertEqual(bare.exchange, Exchange.SSE)

    def test_vt_symbol_to_symbol(self) -> None:
        self.assertEqual(vt_symbol_to_symbol("600519.SSE"), "600519")
        self.assertEqual(vt_symbol_to_symbol("600519.SH"), "600519")


if __name__ == "__main__":
    unittest.main()
