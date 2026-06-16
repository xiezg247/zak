"""悬浮球 UI 层薄集成测试（面板 mode 路由与场景标签）。"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from vnpy.trader.constant import Exchange

from tests.ashare.ai.context.factories import IS_IN_WATCHLIST, WATCHLIST_ROWS
from vnpy_ashare.ai.context import AiContextData, clear_all, enrich_context_with_actions, set_screening_results
from vnpy_ashare.ai.ui.floating_actions import build_quick_actions_for_panel, scene_label_from_context


class FloatingPanelTests(unittest.TestCase):
    def setUp(self) -> None:
        clear_all()

    def tearDown(self) -> None:
        clear_all()

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

    def test_assistant_mode_actions(self) -> None:
        with patch(
            WATCHLIST_ROWS,
            return_value=[("002230", Exchange.SZSE, "科大讯飞")],
        ):
            panel_actions = build_quick_actions_for_panel(AiContextData(page="AI 助手"), mode="assistant")
        ids = [a.id for a in panel_actions]
        self.assertEqual(
            ids,
            [
                "diagnose",
                "team_analysis",
                "technical",
                "trend_forecast",
                "recent_trend",
                "reference_peer",
                "pattern_screen",
                "condition_screen",
            ],
        )

    def test_screener_page_without_results_shows_screen_menus(self) -> None:
        set_screening_results(condition="", rows=[], updated_at=None)
        panel_actions = build_quick_actions_for_panel(AiContextData(page="选股"), mode="floating")
        ids = [a.id for a in panel_actions]
        self.assertEqual(ids, ["pattern_screen", "condition_screen"])

    def test_assistant_panel_prepends_interpret_after_screening(self) -> None:
        set_screening_results(
            condition="形态 · 老鸭头形态",
            rows=[{"vt_symbol": "600519.SSE", "name": "贵州茅台"}],
            updated_at="2026-06-08",
        )
        with patch(
            WATCHLIST_ROWS,
            return_value=[("002230", Exchange.SZSE, "科大讯飞")],
        ):
            panel_actions = build_quick_actions_for_panel(AiContextData(page="AI 助手"), mode="assistant")
        self.assertEqual(panel_actions[0].id, "interpret_screen")
        self.assertEqual(panel_actions[1].id, "diagnose")
        self.assertEqual(len(panel_actions), 9)

    def test_floating_mode_uses_context_symbol(self) -> None:
        with patch(IS_IN_WATCHLIST, return_value=True):
            panel_actions = build_quick_actions_for_panel(
                AiContextData(
                    page="市场",
                    symbol="600519",
                    exchange="上交所",
                    name="贵州茅台",
                ),
                mode="floating",
            )
        ids = [a.id for a in panel_actions]
        self.assertIn("sector_overview", ids)


if __name__ == "__main__":
    unittest.main()
