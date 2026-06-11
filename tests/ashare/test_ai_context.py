"""AI 上下文组装测试。"""

from __future__ import annotations

import unittest

from vnpy.trader.constant import Exchange

from vnpy_ashare.ai.context import build_quote_context, format_quote_summary
from vnpy_ashare.domain.models import StockItem
from vnpy_ashare.quotes import QuoteSnapshot


class TestAiContext(unittest.TestCase):
    def test_format_quote_summary(self) -> None:
        quote = QuoteSnapshot(
            symbol="600519.SH",
            name="贵州茅台",
            last_price=1500.0,
            prev_close=1490.0,
            open_price=1495.0,
            high_price=1510.0,
            low_price=1490.0,
            change_amount=10.0,
            change_pct=0.67,
            turnover_rate=0.5,
            volume=10000.0,
        )
        text = format_quote_summary(quote)
        self.assertIn("1500.00", text)
        self.assertIn("+0.67%", text)

    def test_build_quote_context_with_item(self) -> None:
        item = StockItem(symbol="600519", exchange=Exchange.SSE, name="贵州茅台")
        data = build_quote_context(page="自选", item=item, bar_count=120)
        text = data.to_text()
        self.assertIn("自选", text)
        self.assertIn("贵州茅台", text)
        self.assertIn("600519", text)
        self.assertIn("本地日 K 条数：120", text)

    def test_build_quote_context_empty(self) -> None:
        data = build_quote_context(page="市场", item=None)
        self.assertEqual(data.to_text(), "当前页面：市场")

    def test_build_signals_ai_prompt_uses_custom_windows(self) -> None:
        from vnpy_ashare.ai.context import build_signals_ai_prompt

        prompt = build_signals_ai_prompt(
            "600000.SSE",
            "浦发银行",
            fast_window=8,
            slow_window=21,
        )
        self.assertIn("MA8/MA21", prompt)
        self.assertIn("fast_window=8", prompt)
        self.assertIn("slow_window=21", prompt)


if __name__ == "__main__":
    unittest.main()
