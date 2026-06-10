"""QuoteService 与 context_store 桥接测试。"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

import tests._bootstrap  # noqa: F401
from vnpy_ashare.ai.context import AiContextData
from vnpy_ashare.ai.context_store import clear_all, get_ai_context, set_ai_context
from vnpy_ashare.services.quote_service import QuoteService


class QuoteServiceContextTests(unittest.TestCase):
    def setUp(self) -> None:
        clear_all()
        self.service = QuoteService(MagicMock())

    def tearDown(self) -> None:
        clear_all()

    def test_get_current_context_reads_context_store(self) -> None:
        set_ai_context(
            AiContextData(
                page="自选",
                symbol="600519",
                exchange="SSE",
                name="贵州茅台",
            )
        )
        ctx = self.service.get_current_context()
        self.assertEqual(ctx.symbol, "600519")
        self.assertEqual(ctx.name, "贵州茅台")

    def test_set_current_selection_writes_context_store(self) -> None:
        self.service.set_current_selection(page="市场")
        ctx = get_ai_context()
        self.assertEqual(ctx.page, "市场")
        self.assertEqual(ctx.symbol, "")

    def test_publish_quote_context_writes_context_store(self) -> None:
        from vnpy.trader.constant import Exchange

        from vnpy_ashare.domain.models import StockItem

        item = StockItem(symbol="600519", exchange=Exchange.SSE, name="贵州茅台")
        self.service.publish_quote_context(page="自选", item=item, bar_count=120)
        ctx = get_ai_context()
        self.assertEqual(ctx.page, "自选")
        self.assertEqual(ctx.symbol, "600519")
        self.assertIn("120", ctx.extra)


if __name__ == "__main__":
    unittest.main()
