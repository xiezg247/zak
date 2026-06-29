"""enrich_context_with_actions：badge / chip / actions 路由测试。"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from tests.ashare.ai.context.factories import IS_IN_WATCHLIST, POSITION_CONTAINS, maotai_item, maotai_quote
from vnpy_ashare.ai.context.enrichment import enrich_context_with_actions
from vnpy_ashare.ai.context.quote.assembly import build_quote_context
from vnpy_ashare.ai.context.store import clear_all, set_screening_results
from vnpy_common.ai.protocol import AiContextData


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
        self.assertEqual(len(data.actions), 3)
        ids = [action.id for action in data.actions]
        self.assertEqual(ids, ["quick_analysis", "technical_trend", "peer_ops"])
        self.assertTrue(data.actions[0].has_menu)
        self.assertTrue(data.actions[1].has_menu)
        peer_child_ids = [child.id for child in data.actions[2].children]
        self.assertIn("note_review", peer_child_ids)

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
        self.assertEqual(data.actions[1].id, "screener_radar_leader")
        self.assertEqual(data.actions[2].id, "screener_radar_resonance")
        self.assertEqual(data.actions[3].id, "pattern_screen")
        self.assertEqual(len(data.actions), 5)

    def test_data_manager_badge_and_action(self) -> None:
        extra = "你正在协助用户查看本地 K 线数据覆盖；请基于工具与上下文回答，禁止编造。\n日线：12 组标的，共 3456 根 K 线\n分钟线：3 组标的，共 890 根 K 线"
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
        self.assertEqual(ids[:2], ["market_environment", "intraday_environment"])
        self.assertEqual(ids[2:5], ["quick_analysis", "technical_trend", "peer_ops"])
        peer_ops = data.actions[4]
        peer_child_ids = [c.id for c in peer_ops.children]
        self.assertIn("sector_overview", peer_child_ids)
        self.assertNotIn("add_watchlist", peer_child_ids)

    def test_radar_page_with_symbol_keeps_insight(self) -> None:
        with patch(IS_IN_WATCHLIST, return_value=True):
            data = enrich_context_with_actions(
                AiContextData(
                    page="雷达",
                    symbol="600519",
                    exchange="上交所",
                    name="贵州茅台",
                )
            )
        ids = [a.id for a in data.actions]
        self.assertEqual(ids[0], "radar_insight")
        self.assertEqual(ids[1:4], ["quick_analysis", "technical_trend", "peer_ops"])

    def test_sector_flow_page_actions(self) -> None:
        data = enrich_context_with_actions(AiContextData(page="板块资金", extra="板块资金监控页"))
        self.assertEqual(data.badge, "板块资金")
        ids = [a.id for a in data.actions]
        self.assertEqual(
            ids,
            ["sector_flow_structure", "sector_flow_rotation", "sector_flow_radar_leader"],
        )

    def test_backtest_page_actions(self) -> None:
        data = enrich_context_with_actions(AiContextData(page="策略回测", symbol="600519", exchange="SSE", extra="回测摘要"))
        self.assertEqual(data.badge, "策略回测")
        ids = [a.id for a in data.actions]
        self.assertEqual(ids, ["interpret_backtest", "backtest_param_hint", "backtest_risk_review"])

    def test_batch_compare_page_actions(self) -> None:
        data = enrich_context_with_actions(AiContextData(page="回测对比", extra="批次统计"))
        ids = [a.id for a in data.actions]
        self.assertEqual(ids, ["interpret_batch_compare", "batch_attribution"])

    def test_watchlist_without_symbol_actions(self) -> None:
        data = enrich_context_with_actions(AiContextData(page="自选"))
        ids = [a.id for a in data.actions]
        self.assertEqual(ids[:2], ["watchlist_portfolio", "watchlist_intraday_env"])
        self.assertIn("未选中个股", data.chip_text)

    def test_sector_flow_chip_text(self) -> None:
        extra = "板块资金监控页\n行业·盘中估算\n净流入 半导体 +12.3亿；净流出 银行 -8.1亿"
        data = enrich_context_with_actions(AiContextData(page="板块资金", extra=extra))
        self.assertIn("流入 半导体", data.chip_text)

    def test_backtest_chip_text(self) -> None:
        extra = "你正在协助用户解读 A 股策略回测结果；请基于回测摘要与工具数据回答，禁止编造指标。\n当前表单：策略 双均线 · 标的 600519.SSE · 周期 日线"
        data = enrich_context_with_actions(AiContextData(page="策略回测", extra=extra))
        self.assertIn("双均线", data.chip_text)
        self.assertIn("600519", data.chip_text)

    def test_playbook_page_actions(self) -> None:
        data = enrich_context_with_actions(AiContextData(page="守则", extra="playbook"))
        ids = [a.id for a in data.actions]
        self.assertEqual(ids, ["discipline_one_liner", "plan_review", "position_discipline"])


if __name__ == "__main__":
    unittest.main()
