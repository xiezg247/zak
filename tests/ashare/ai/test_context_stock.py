"""AiContextData 标的解析。"""

from __future__ import annotations

import unittest

from vnpy_ashare.ai.context.context_stock import context_stock_from_ai, resolve_exchange_label
from vnpy_common.ai.protocol import AiContextData


class ContextStockFromAiTests(unittest.TestCase):
    def test_resolve_exchange_label_enum_name(self) -> None:
        exchange = resolve_exchange_label("SSE")
        self.assertIsNotNone(exchange)
        assert exchange is not None
        self.assertEqual(exchange.name, "SSE")

    def test_resolve_exchange_label_cn_name(self) -> None:
        exchange = resolve_exchange_label("上交所")
        self.assertIsNotNone(exchange)
        assert exchange is not None
        self.assertEqual(exchange.name, "SSE")

    def test_context_stock_from_ai_quotes_page(self) -> None:
        data = AiContextData(page="自选", symbol="002230", exchange="深交所", name="科大讯飞")
        resolved = context_stock_from_ai(data)
        self.assertIsNotNone(resolved)
        assert resolved is not None
        symbol, exchange, name = resolved
        self.assertEqual(symbol, "002230")
        self.assertEqual(exchange.name, "SZSE")
        self.assertEqual(name, "科大讯飞")


if __name__ == "__main__":
    unittest.main()
