"""enrich_context_with_actions：badge / chip / actions 路由测试。"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from tests.ashare.ai.context.factories import IS_IN_WATCHLIST, POSITION_CONTAINS, maotai_item, maotai_quote
from vnpy_ashare.ai.context import (
    AiContextData,
    build_quote_context,
    clear_all,
    enrich_context_with_actions,
    set_screening_results,
)


class TestEnrichment(unittest.TestCase):
    def setUp(self) -> None:
        clear_all()

    def tearDown(self) -> None:
        clear_all()

    def test_watchlist_badge_and_chip(self) -> None:
        with patch(POSITION_CONTAINS, return_value=False):
            raw = build_quote_context(
                page="自选",
                item=maotai_item(),
                quote=maotai_quote(),
                bar_count=120,
            )
            data = enrich_context_with_actions(raw)

        self.assertEqual(data.badge, "自选")
        self.assertIn("贵州茅台", data.chip_text)
        self.assertIn("+2.30%", data.chip_text)
        self.assertEqual(len(data.actions), 5)
        self.assertTrue(all(action.has_menu for action in data.actions[:4]))
        self.assertEqual(data.actions[4].id, "reference_peer")

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
        self.assertTrue(data.actions[0].auto_send)
        self.assertEqual(data.actions[1].id, "pattern_screen")
        self.assertEqual(len(data.actions), 3)

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

    def test_market_page_enrichment_actions(self) -> None:
        with patch(IS_IN_WATCHLIST, return_value=True):
            data = enrich_context_with_actions(
                AiContextData(
                    page="市场",
                    symbol="600519",
                    exchange="上交所",
                    name="贵州茅台",
                )
            )
        ids = [a.id for a in data.actions]
        self.assertIn("sector_overview", ids)
        self.assertNotIn("add_watchlist", ids)


if __name__ == "__main__":
    unittest.main()
