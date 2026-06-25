"""快捷菜单与 page extras 组装测试。"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from vnpy.trader.constant import Exchange

from tests.ashare.ai.context.factories import (
    IS_IN_WATCHLIST,
    POSITION_CONTAINS,
    WATCHLIST_ROWS,
    maotai_binding,
)
from vnpy_ashare.ai.context.quote.assembly import (
    build_assistant_quick_actions,
    build_bound_stock_menus,
    build_floating_stock_quick_actions,
    build_peer_ops_menu,
)
from vnpy_ashare.ai.context.quote.prompts import build_team_analysis_ai_prompt


def _child_ids(action) -> list[str]:
    return [child.id for child in action.children]


class TestQuoteActions(unittest.TestCase):
    def test_bound_stock_menus_structure(self) -> None:
        binding = maotai_binding()
        with patch(WATCHLIST_ROWS, return_value=[(binding.symbol, Exchange.SSE, binding.name)]):
            actions = build_assistant_quick_actions()
        self.assertEqual(len(actions), 5)
        stock_ids = [a.id for a in actions[:2]]
        self.assertEqual(stock_ids, ["quick_analysis", "technical_trend"])
        self.assertEqual(actions[2].id, "peer_ops")
        screen_ids = [a.id for a in actions[3:]]
        self.assertEqual(screen_ids, ["pattern_screen", "condition_screen"])

        quick = actions[0]
        self.assertTrue(quick.has_menu)
        quick_child_ids = _child_ids(quick)
        self.assertEqual(
            quick_child_ids,
            ["diagnose_full", "diagnose_finance", "diagnose_flow", "team_analysis"],
        )
        team = next(c for c in quick.children if c.id == "team_analysis")
        self.assertFalse(team.auto_send)

        technical_trend = actions[1]
        self.assertTrue(technical_trend.has_menu)
        self.assertEqual(
            [child.label for child in technical_trend.children[:3]],
            ["技术·均线量比", "技术·MACD/KDJ/RSI", "技术·双均线信号"],
        )
        self.assertIn("走势·近20日", [child.label for child in technical_trend.children])
        trend_children = [c for c in technical_trend.children if c.id.startswith("trend_")]
        self.assertTrue(trend_children)
        self.assertFalse(any(child.auto_send for child in trend_children))

        peer_ops = actions[2]
        self.assertEqual(
            _child_ids(peer_ops)[:3],
            ["ref_peer_10", "ref_peer_20", "ref_peer_30"],
        )
        self.assertIn("600519.SSE", peer_ops.children[1].prompt)
        self.assertIn("标杆", peer_ops.children[1].prompt)

        pattern = next(a for a in actions if a.id == "pattern_screen")
        self.assertEqual(
            [child.label for child in pattern.children],
            ["老鸭头形态", "均线多头", "W底形态", "主题投资"],
        )
        condition = next(a for a in actions if a.id == "condition_screen")
        self.assertEqual(
            [child.label for child in condition.children],
            ["盘中多因子", "盘后多因子", "低 PE", "主力净流入", "成交量放大"],
        )
        short_hot = next(c for c in condition.children if c.id == "cond_short_hot")
        self.assertIn("盘中多因子选股", short_hot.prompt)
        self.assertIn("盘中多因子", short_hot.prompt)
        self.assertFalse(short_hot.auto_send)
        mid_swing = next(c for c in condition.children if c.id == "cond_mid_swing")
        self.assertIn("盘后多因子选股", mid_swing.prompt)
        growth = next(c for c in condition.children if c.id == "cond_growth")
        self.assertIn("主力净流入", growth.prompt)

    def test_floating_bound_to_selected_symbol(self) -> None:
        with patch(POSITION_CONTAINS, return_value=False):
            actions = build_floating_stock_quick_actions(
                "002230",
                exchange_cn="深交所",
                name="科大讯飞",
                page="自选",
            )
        self.assertEqual(len(actions), 3)
        self.assertEqual([a.id for a in actions], ["quick_analysis", "technical_trend", "peer_ops"])
        self.assertIn("002230.SZSE", actions[0].children[0].prompt)
        team = next(c for c in actions[0].children if c.id == "team_analysis")
        self.assertIn("投研团队全面分析", team.prompt)
        self.assertIn("600519.SSE", build_team_analysis_ai_prompt("600519.SSE", "贵州茅台"))
        peer_child_ids = _child_ids(actions[2])
        self.assertIn("note_review", peer_child_ids)

    def test_market_page_includes_sector_overview(self) -> None:
        with patch(IS_IN_WATCHLIST, return_value=True):
            actions = build_floating_stock_quick_actions(
                "600519",
                exchange_cn="上交所",
                name="贵州茅台",
                page="市场",
            )
        peer_ops = next(a for a in actions if a.id == "peer_ops")
        peer_child_ids = _child_ids(peer_ops)
        self.assertIn("sector_overview", peer_child_ids)
        self.assertNotIn("add_watchlist", peer_child_ids)

    def test_local_page_includes_bar_health(self) -> None:
        with patch(IS_IN_WATCHLIST, return_value=True):
            actions = build_floating_stock_quick_actions(
                "600519",
                exchange_cn="上交所",
                name="贵州茅台",
                page="本地",
                extra="本地日 K 条数：120",
            )
        peer_ops = next(a for a in actions if a.id == "peer_ops")
        bar_health = next(c for c in peer_ops.children if c.id == "bar_health")
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
        peer_ops = next(a for a in actions if a.id == "peer_ops")
        add = next(c for c in peer_ops.children if c.id == "add_watchlist")
        self.assertIn("加入自选池", add.prompt)

    def test_bound_stock_menus_count(self) -> None:
        binding = maotai_binding()
        menus = build_bound_stock_menus(binding)
        self.assertEqual(len(menus), 2)
        self.assertEqual([m.id for m in menus], ["quick_analysis", "technical_trend"])

    def test_peer_ops_menu_without_page(self) -> None:
        binding = maotai_binding()
        menu = build_peer_ops_menu(binding)
        self.assertEqual(menu.id, "peer_ops")
        self.assertEqual(len(menu.children), 3)


if __name__ == "__main__":
    unittest.main()
