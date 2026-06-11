"""悬浮球上下文增强单元测试。"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from vnpy.trader.constant import Exchange

from vnpy_ashare.ai.context import (
    AiContextData,
    StockBinding,
    build_assistant_quick_actions,
    build_floating_stock_quick_actions,
    build_quote_context,
    enrich_context_with_actions,
    resolve_assistant_stock_binding,
    set_screening_results,
)
from vnpy_ashare.ai.ui.floating_actions import (
    build_quick_actions_for_panel,
    scene_label_from_context,
)
from vnpy_ashare.domain.symbols import StockItem
from vnpy_ashare.quotes import QuoteSnapshot


class FloatingActionsTests(unittest.TestCase):
    def test_assistant_default_fallback_binding(self) -> None:
        with patch("vnpy_ashare.ai.context.quote.load_watchlist_rows", return_value=[]):
            binding = resolve_assistant_stock_binding()
        self.assertEqual(binding.vt_symbol, "002230.SZSE")
        self.assertEqual(binding.name, "科大讯飞")

    def test_assistant_watchlist_first_binding(self) -> None:
        with patch(
            "vnpy_ashare.ai.context.quote.load_watchlist_rows",
            return_value=[("600519", Exchange.SSE, "贵州茅台")],
        ):
            binding = resolve_assistant_stock_binding()
        self.assertEqual(binding.vt_symbol, "600519.SSE")

    def test_assistant_four_menus_with_children(self) -> None:
        binding = StockBinding(
            symbol="600519",
            exchange_cn="上交所",
            name="贵州茅台",
            vt_symbol="600519.SSE",
        )
        with patch(
            "vnpy_ashare.ai.context.quote.resolve_assistant_stock_binding",
            return_value=binding,
        ):
            actions = build_assistant_quick_actions()
        self.assertEqual(len(actions), 7)
        stock_ids = [a.id for a in actions[:4]]
        screen_ids = [a.id for a in actions[4:]]
        self.assertEqual(stock_ids, ["diagnose", "technical", "trend_forecast", "recent_trend"])
        self.assertEqual(screen_ids, ["pattern_screen", "condition_screen", "reference_screen"])
        for action in actions:
            self.assertTrue(action.has_menu, action.id)
        pattern = next(a for a in actions if a.id == "pattern_screen")
        self.assertEqual(
            [child.label for child in pattern.children],
            ["老鸭头形态", "均线多头", "W底形态", "主题投资"],
        )
        condition = next(a for a in actions if a.id == "condition_screen")
        self.assertEqual(
            [child.label for child in condition.children],
            ["中线波段", "短线游资", "长线价投"],
        )
        reference = next(a for a in actions if a.id == "reference_screen")
        self.assertEqual(
            [child.label for child in reference.children],
            ["短线波段", "长线价值", "成长赛道", "周期资源"],
        )
        trend = next(a for a in actions if a.id == "trend_forecast")
        self.assertIn("600519.SSE", trend.children[0].prompt)
        self.assertIn("screen_by_pattern", pattern.children[0].prompt)

    def test_floating_bound_to_selected_symbol(self) -> None:
        actions = build_floating_stock_quick_actions(
            "002230",
            exchange_cn="深交所",
            name="科大讯飞",
            page="自选",
        )
        self.assertEqual(len(actions), 4)
        self.assertIn("002230.SZSE", actions[0].children[0].prompt)

    def test_market_page_includes_sector_overview(self) -> None:
        with patch("vnpy_ashare.ai.context.quote.is_symbol_in_watchlist", return_value=True):
            actions = build_floating_stock_quick_actions(
                "600519",
                exchange_cn="上交所",
                name="贵州茅台",
                page="市场",
            )
        ids = [a.id for a in actions]
        self.assertIn("sector_overview", ids)
        self.assertNotIn("add_watchlist", ids)

    def test_local_page_includes_bar_health(self) -> None:
        with patch("vnpy_ashare.ai.context.quote.is_symbol_in_watchlist", return_value=True):
            actions = build_floating_stock_quick_actions(
                "600519",
                exchange_cn="上交所",
                name="贵州茅台",
                page="本地",
                extra="本地日 K 条数：120",
            )
        bar_health = next(a for a in actions if a.id == "bar_health")
        self.assertIn("get_bars_summary", bar_health.prompt)
        self.assertIn("600519.SSE", bar_health.prompt)

    def test_non_watchlist_symbol_shows_add_watchlist(self) -> None:
        with patch("vnpy_ashare.ai.context.quote.is_symbol_in_watchlist", return_value=False):
            actions = build_floating_stock_quick_actions(
                "000001",
                exchange_cn="深交所",
                name="平安银行",
                page="市场",
            )
        add = next(a for a in actions if a.id == "add_watchlist")
        self.assertIn("add_to_watchlist", add.prompt)

    def test_scene_label_from_context(self) -> None:
        data = enrich_context_with_actions(
            AiContextData(
                page="市场",
                symbol="600519",
                exchange="上交所",
                name="贵州茅台",
            )
        )
        self.assertEqual(scene_label_from_context(data), "市场 · 贵州茅台")

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
        self.assertEqual(len(data.actions), 4)
        self.assertTrue(all(action.has_menu for action in data.actions))

    def test_assistant_mode_actions(self) -> None:
        binding = StockBinding(
            symbol="002230",
            exchange_cn="深交所",
            name="科大讯飞",
            vt_symbol="002230.SZSE",
        )
        with patch(
            "vnpy_ashare.ai.context.quote.resolve_assistant_stock_binding",
            return_value=binding,
        ):
            panel_actions = build_quick_actions_for_panel(AiContextData(page="AI 助手"), mode="assistant")
        ids = [a.id for a in panel_actions]
        self.assertEqual(
            ids,
            [
                "diagnose",
                "technical",
                "trend_forecast",
                "recent_trend",
                "pattern_screen",
                "condition_screen",
                "reference_screen",
            ],
        )

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
        extra = "你正在协助用户查看本地 K 线数据覆盖；请基于工具与上下文回答，禁止编造。\n日线：12 组标的，共 3456 根 K 线\n分钟线：3 组标的，共 890 根 K 线"
        data = enrich_context_with_actions(AiContextData(page="数据管理", extra=extra))

        self.assertEqual(data.badge, "数据")
        self.assertIn("12 组标的", data.chip_text)
        self.assertEqual(len(data.actions), 1)
        self.assertEqual(data.actions[0].id, "data_gap")


if __name__ == "__main__":
    unittest.main()
