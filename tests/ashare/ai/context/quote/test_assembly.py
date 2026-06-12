"""AiContextData 组装与标的绑定测试。"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from vnpy.trader.constant import Exchange

from tests.ashare.ai.context.factories import WATCHLIST_ROWS, maotai_item, pudong_item
from vnpy_ashare.ai.context import build_quote_context, resolve_assistant_stock_binding


class TestQuoteAssembly(unittest.TestCase):
    def test_build_quote_context_with_item(self) -> None:
        data = build_quote_context(page="自选", item=maotai_item(), bar_count=120)
        text = data.to_text()
        self.assertIn("自选", text)
        self.assertIn("贵州茅台", text)
        self.assertIn("600519", text)
        self.assertIn("本地日 K 条数：120", text)

    def test_build_quote_context_empty(self) -> None:
        data = build_quote_context(page="市场", item=None)
        self.assertEqual(data.to_text(), "当前页面：市场")

    def test_build_quote_context_includes_signal_extra(self) -> None:
        data = build_quote_context(
            page="自选",
            item=pudong_item(),
            bar_count=120,
            signal_extra="策略信号：买入\n参考买价：10.00",
        )
        text = data.to_text()
        self.assertIn("策略信号：买入", text)
        self.assertIn("参考买价：10.00", text)

    def test_assistant_default_fallback_binding(self) -> None:
        with patch(WATCHLIST_ROWS, return_value=[]):
            binding = resolve_assistant_stock_binding()
        self.assertEqual(binding.vt_symbol, "002230.SZSE")
        self.assertEqual(binding.name, "科大讯飞")

    def test_assistant_watchlist_first_binding(self) -> None:
        with patch(
            WATCHLIST_ROWS,
            return_value=[("600519", Exchange.SSE, "贵州茅台")],
        ):
            binding = resolve_assistant_stock_binding()
        self.assertEqual(binding.vt_symbol, "600519.SSE")


if __name__ == "__main__":
    unittest.main()
