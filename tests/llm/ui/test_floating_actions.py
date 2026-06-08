"""悬浮球上下文增强单元测试。"""

from __future__ import annotations

import unittest

from vnpy.trader.constant import Exchange

from vnpy_ashare.ai.context import AiContextData
from vnpy_ashare.ai.session_context import set_screening_results
from vnpy_ashare.models import StockItem
from vnpy_ashare.quotes import QuoteSnapshot
from vnpy_ashare.ai.context import build_quote_context, format_quote_summary
from vnpy_llm.ui.floating_actions import enrich_context_with_actions


class FloatingActionsTests(unittest.TestCase):
    def test_watchlist_badge_and_chip(self) -> None:
        item = StockItem(symbol="600519", exchange=Exchange.SSE, name="贵州茅台")
        quote = QuoteSnapshot(
            symbol="600519",
            name="贵州茅台",
            last_price=1688.0,
            change_amount=38.0,
            change_pct=2.3,
            open_price=1650.0,
            high_price=1695.0,
            low_price=1648.0,
            prev_close=1650.0,
            turnover_rate=0.5,
            volume=1_000_000.0,
        )
        raw = build_quote_context(page="自选", item=item, quote=quote, bar_count=120)
        data = enrich_context_with_actions(raw)

        self.assertEqual(data.badge, "自选")
        self.assertIn("贵州茅台", data.chip_text)
        self.assertIn("+2.30%", data.chip_text)
        self.assertEqual(len(data.actions), 2)
        self.assertEqual(data.actions[0].id, "diagnose")
        self.assertEqual(data.actions[1].id, "technical")

    def test_screener_badge_with_count(self) -> None:
        set_screening_results(
            condition="高股息",
            rows=[{"vt_symbol": "600519.SH", "name": "贵州茅台"}],
            updated_at="2026-06-08",
        )
        data = enrich_context_with_actions(AiContextData(page="选股", extra="test"))

        self.assertEqual(data.badge, "选股·1")
        self.assertIn("命中 1 条", data.chip_text)
        self.assertEqual(data.actions[0].id, "interpret_screen")

    def test_data_manager_badge_and_action(self) -> None:
        extra = (
            "你正在协助用户查看本地 K 线数据覆盖；请基于工具与上下文回答，禁止编造。\n"
            "日线：12 组标的，共 3456 根 K 线\n"
            "分钟线：3 组标的，共 890 根 K 线"
        )
        data = enrich_context_with_actions(AiContextData(page="数据管理", extra=extra))

        self.assertEqual(data.badge, "数据")
        self.assertIn("12 组标的", data.chip_text)
        self.assertEqual(len(data.actions), 1)
        self.assertEqual(data.actions[0].id, "data_gap")


if __name__ == "__main__":
    unittest.main()
