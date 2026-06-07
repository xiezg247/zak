"""策略回测导航事件。"""

from __future__ import annotations

import unittest

from vnpy.trader.constant import Exchange

from vnpy_ashare.events import BacktestRequest, EVENT_OPEN_BACKTEST
from vnpy_ashare.models import StockItem


class BacktestRequestTest(unittest.TestCase):
    def test_vt_symbol_from_stock_item(self) -> None:
        item = StockItem("600519", Exchange.SSE, "贵州茅台")
        req = BacktestRequest(
            vt_symbol=item.vt_symbol,
            source_page="自选",
            name=item.name,
        )
        self.assertEqual(req.vt_symbol, "600519.SSE")
        self.assertEqual(req.source_page, "自选")

    def test_event_name(self) -> None:
        self.assertEqual(EVENT_OPEN_BACKTEST, "eOpenBacktest")
