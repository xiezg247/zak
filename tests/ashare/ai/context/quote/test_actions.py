"""快捷菜单与 page extras 组装测试。"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from tests.ashare.ai.context.factories import (
    IS_IN_WATCHLIST,
    POSITION_CONTAINS,
    maotai_binding,
)
from vnpy_ashare.ai.context.quote import (
    build_assistant_screening_menus,
    build_bound_stock_menus,
    build_floating_stock_quick_actions,
    build_reference_peer_menu,
)


class TestQuoteActions(unittest.TestCase):
    def test_bound_stock_menus_structure(self) -> None:
        binding = maotai_binding()
        actions = [
            *build_bound_stock_menus(binding),
            build_reference_peer_menu(binding),
            *build_assistant_screening_menus(),
        ]
        self.assertEqual(len(actions), 7)
        stock_ids = [a.id for a in actions[:4]]
        screen_ids = [a.id for a in actions[5:]]
        self.assertEqual(stock_ids, ["diagnose", "technical", "trend_forecast", "recent_trend"])
        self.assertEqual(actions[4].id, "reference_peer")
        self.assertEqual(screen_ids, ["pattern_screen", "condition_screen"])
        for action in actions:
            self.assertTrue(action.has_menu, action.id)

        pattern = next(a for a in actions if a.id == "pattern_screen")
        self.assertEqual(
            [child.label for child in pattern.children],
            ["老鸭头形态", "均线多头", "W底形态", "热点活跃"],
        )
        condition = next(a for a in actions if a.id == "condition_screen")
        self.assertEqual(
            [child.label for child in condition.children],
            ["短线游资", "中线波段", "长线价投", "成长赛道", "周期资源"],
        )
        short_hot = next(c for c in condition.children if c.id == "cond_short_hot")
        self.assertIn("盘中多因子选股", short_hot.prompt)
        self.assertIn("短线游资", short_hot.prompt)
        self.assertTrue(short_hot.auto_send)
        mid_swing = next(c for c in condition.children if c.id == "cond_mid_swing")
        self.assertIn("盘后多因子选股", mid_swing.prompt)
        long_value = next(c for c in condition.children if c.id == "cond_long_value")
        self.assertIn("低 PE", long_value.prompt)
        self.assertIn("长线价投", long_value.prompt)

        reference_peer = next(a for a in actions if a.id == "reference_peer")
        self.assertEqual(
            [child.label for child in reference_peer.children],
            ["Top 10", "Top 20", "Top 30"],
        )
        self.assertIn("600519.SSE", reference_peer.children[1].prompt)
        self.assertIn("标杆", reference_peer.children[1].prompt)

        trend = next(a for a in actions if a.id == "trend_forecast")
        self.assertIn("600519.SSE", trend.children[0].prompt)
        self.assertIn("情景分析", trend.children[0].prompt)
        self.assertIn("乐观/基准/悲观", trend.children[0].prompt)
        self.assertTrue(all(child.auto_send for child in trend.children))
        self.assertIn("形态选股", pattern.children[0].prompt)
        self.assertTrue(pattern.children[0].auto_send)

    def test_floating_bound_to_selected_symbol(self) -> None:
        with patch(POSITION_CONTAINS, return_value=False):
            actions = build_floating_stock_quick_actions(
                "002230",
                exchange_cn="深交所",
                name="科大讯飞",
                page="自选",
            )
        self.assertEqual(len(actions), 5)
        self.assertIn("002230.SZSE", actions[0].children[0].prompt)

    def test_market_page_includes_sector_overview(self) -> None:
        with patch(IS_IN_WATCHLIST, return_value=True):
            actions = build_floating_stock_quick_actions(
                "600519",
                exchange_cn="上交所",
                name="贵州茅台",
                page="市场",
            )
        ids = [a.id for a in actions]
        self.assertIn("reference_peer", ids)
        self.assertIn("sector_overview", ids)
        self.assertNotIn("add_watchlist", ids)

    def test_local_page_includes_bar_health(self) -> None:
        with patch(IS_IN_WATCHLIST, return_value=True):
            actions = build_floating_stock_quick_actions(
                "600519",
                exchange_cn="上交所",
                name="贵州茅台",
                page="本地",
                extra="本地日 K 条数：120",
            )
        bar_health = next(a for a in actions if a.id == "bar_health")
        self.assertIn("本地日 K", bar_health.prompt)
        self.assertIn("600519.SSE", bar_health.prompt)

    def test_non_watchlist_symbol_shows_add_watchlist(self) -> None:
        with patch(IS_IN_WATCHLIST, return_value=False):
            actions = build_floating_stock_quick_actions(
                "000001",
                exchange_cn="深交所",
                name="平安银行",
                page="市场",
            )
        add = next(a for a in actions if a.id == "add_watchlist")
        self.assertIn("加入自选池", add.prompt)


if __name__ == "__main__":
    unittest.main()
