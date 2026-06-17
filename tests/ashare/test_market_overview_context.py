"""market_overview AI 上下文测试。"""

from __future__ import annotations

import unittest

from vnpy_ashare.ai.context.enrichment import enrich_context_with_actions
from vnpy_ashare.ai.context.market_overview import (
    format_market_overview_extra,
    merge_market_overview_extra,
    sync_market_overview_context,
)
from vnpy_ashare.ai.context.store import clear_all, get_market_overview_context
from vnpy_ashare.domain.market.quote_snapshot import QuoteSnapshot
from vnpy_ashare.quotes.market.market_breadth import MarketBreadthSnapshot
from vnpy_ashare.quotes.market.market_environment import MarketEnvironmentSnapshot
from vnpy_ashare.quotes.market.market_overview_loaders import MarketOverviewData, SectorRankItem
from vnpy_common.ai.protocol import AiContextData


def _quote(symbol: str, pct: float) -> QuoteSnapshot:
    return QuoteSnapshot(
        symbol=symbol,
        name=symbol,
        last_price=3000.0,
        prev_close=2990.0,
        open_price=2995.0,
        high_price=3010.0,
        low_price=2988.0,
        change_amount=10.0,
        change_pct=pct,
        turnover_rate=0.0,
        volume=0.0,
        amount=0.0,
    )


class MarketOverviewContextTests(unittest.TestCase):
    def setUp(self) -> None:
        clear_all()

    def tearDown(self) -> None:
        clear_all()

    def test_format_and_merge_extra(self) -> None:
        data = MarketOverviewData(
            indices=[("上证指数", _quote("000001.SH", 0.8))],
            breadth=MarketBreadthSnapshot(100, 80, 5, 3, 1, 1e10, 185, updated_at="12:00"),
            sectors=[SectorRankItem("银行", 12, 2.5)],
            environment=MarketEnvironmentSnapshot(52.0, "中性", 1234.0, "20250612"),
        )
        sync_market_overview_context(data)
        extra = format_market_overview_extra()
        self.assertIn("【大盘概览】", extra)
        self.assertIn("上证指数", extra)
        self.assertIn("恐贪", extra)
        self.assertIn("北向", extra)
        merged = merge_market_overview_extra("本地日 K 条数：120")
        self.assertIn("【大盘概览】", merged)
        self.assertIn("本地日 K", merged)

    def test_market_page_quick_actions_without_symbol(self) -> None:
        sync_market_overview_context(
            MarketOverviewData(
                indices=[],
                breadth=None,
                sectors=[],
                environment=MarketEnvironmentSnapshot(40.0, "恐惧", None, ""),
            )
        )
        data = enrich_context_with_actions(AiContextData(page="市场"))
        ids = [action.id for action in data.actions]
        self.assertEqual(ids[:2], ["market_environment", "industry_momentum"])
        self.assertEqual(len(ids), 2)

    def test_get_market_overview_context_returns_copy(self) -> None:
        sync_market_overview_context(
            MarketOverviewData(
                indices=[("上证", _quote("000001.SH", 1.0))],
                breadth=None,
                sectors=[],
                environment=None,
            )
        )
        ctx = get_market_overview_context()
        assert ctx is not None
        ctx["index_lines"] = []
        self.assertTrue(get_market_overview_context()["index_lines"])


if __name__ == "__main__":
    unittest.main()
