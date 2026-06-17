"""标的模型与回测导航事件测试。"""

from __future__ import annotations

import unittest

from vnpy.trader.constant import Exchange

from vnpy_ashare.app.events import EVENT_OPEN_BACKTEST, BacktestRequest
from vnpy_ashare.domain.symbols import StockItem, parse_tickflow_symbol


class TestStockItem(unittest.TestCase):
    def test_vt_symbol(self) -> None:
        item = StockItem(symbol="600519", exchange=Exchange.SSE, name="贵州茅台")
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


class BacktestRequestTest(unittest.TestCase):
    def test_vt_symbol_from_stock_item(self) -> None:
        item = StockItem(symbol="600519", exchange=Exchange.SSE, name="贵州茅台")
        req = BacktestRequest(
            vt_symbol=item.vt_symbol,
            source_page="自选",
            name=item.name,
        )
        self.assertEqual(req.vt_symbol, "600519.SSE")
        self.assertEqual(req.source_page, "自选")

    def test_event_name(self) -> None:
        self.assertEqual(EVENT_OPEN_BACKTEST, "eOpenBacktest")


if __name__ == "__main__":
    unittest.main()
