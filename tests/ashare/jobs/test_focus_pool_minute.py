"""关注池与 1m K 缺口检测测试。"""

from __future__ import annotations

import unittest
from datetime import datetime
from unittest.mock import patch

from vnpy.trader.constant import Exchange

from vnpy_ashare.data.bar_health import BarMeta
from vnpy_ashare.domain.symbols.stock import StockItem
from vnpy_ashare.jobs.bars.focus_pool_minute import (
    classify_minute_bar_need,
    select_minute_fill_targets,
    summarize_minute_gaps,
)
from vnpy_ashare.services.focus_pool import load_focus_pool_stock_items


class FocusPoolSymbolsTest(unittest.TestCase):
    @patch("vnpy_ashare.services.focus_pool.load_position_rows")
    @patch("vnpy_ashare.services.focus_pool.load_watchlist_group_member_keys")
    @patch("vnpy_ashare.services.focus_pool.load_watchlist_groups")
    @patch("vnpy_ashare.services.focus_pool.load_watchlist_rows")
    def test_load_focus_pool_merges_observation_and_positions(
        self,
        mock_watchlist_rows,
        mock_groups,
        mock_member_keys,
        mock_positions,
    ) -> None:
        from vnpy_ashare.storage.repositories.watchlist_groups import WatchlistGroupRecord

        mock_watchlist_rows.return_value = [("600000", Exchange.SSE, "浦发银行")]
        mock_groups.return_value = [
            WatchlistGroupRecord(id="g1", name="短线观察", sort_order=0, position_cap_pct=None),
        ]
        mock_member_keys.return_value = {("600000", "SSE"), ("000001", "SZSE")}
        mock_positions.return_value = [
            {"symbol": "000001", "exchange": "SZSE"},
            {"symbol": "600519", "exchange": "SSE"},
        ]

        items = load_focus_pool_stock_items()
        symbols = [item.vt_symbol for item in items]
        self.assertEqual(symbols, ["000001.SZSE", "600000.SSE", "600519.SSE"])


class MinuteGapTest(unittest.TestCase):
    def test_classify_missing_without_meta(self) -> None:
        item = StockItem(symbol="600000", exchange=Exchange.SSE, name="")
        with patch("vnpy_ashare.jobs.bars.focus_pool_minute.get_scope_overview", return_value=None):
            self.assertEqual(classify_minute_bar_need(item, None), "missing")

    def test_classify_stale(self) -> None:
        item = StockItem(symbol="600000", exchange=Exchange.SSE, name="")
        meta = BarMeta(
            start=datetime(2025, 1, 1),
            end=datetime(2020, 1, 2),
            count=100,
        )
        self.assertEqual(classify_minute_bar_need(item, meta), "stale")

    def test_summarize_and_select_targets(self) -> None:
        items = [
            StockItem(symbol="600000", exchange=Exchange.SSE, name=""),
            StockItem(symbol="000001", exchange=Exchange.SZSE, name=""),
        ]
        meta = {
            (items[0].symbol, items[0].exchange): BarMeta(
                start=datetime(2025, 1, 1),
                end=datetime(2020, 1, 2),
                count=10,
            ),
        }
        with patch("vnpy_ashare.jobs.bars.focus_pool_minute.build_minute_bar_meta", return_value=meta):
            with patch("vnpy_ashare.jobs.bars.focus_pool_minute.get_scope_overview", return_value=None):
                summary = summarize_minute_gaps(items)
                self.assertEqual(summary.total, 2)
                self.assertEqual(summary.needs_fill, 2)
                targets = select_minute_fill_targets(items, meta)
                self.assertEqual(len(targets), 2)


if __name__ == "__main__":
    unittest.main()
