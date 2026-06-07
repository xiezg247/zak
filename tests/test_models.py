"""标的模型测试。"""

from __future__ import annotations

import unittest

from vnpy.trader.constant import Exchange

from vnpy_ashare.models import StockItem, parse_tickflow_symbol


class TestStockItem(unittest.TestCase):
    def test_vt_symbol(self) -> None:
        item = StockItem("600519", Exchange.SSE, "贵州茅台")
        self.assertEqual(item.vt_symbol, "600519.SSE")
        self.assertEqual(item.tickflow_symbol, "600519.SH")

    def test_parse_tickflow_symbol(self) -> None:
        item = parse_tickflow_symbol("000001.SZ", "平安银行")
        assert item is not None
        self.assertEqual(item.symbol, "000001")
        self.assertEqual(item.exchange, Exchange.SZSE)
        self.assertEqual(item.name, "平安银行")

    def test_parse_invalid_symbol(self) -> None:
        self.assertIsNone(parse_tickflow_symbol("invalid"))
        self.assertIsNone(parse_tickflow_symbol("600000.XX"))


if __name__ == "__main__":
    unittest.main()
