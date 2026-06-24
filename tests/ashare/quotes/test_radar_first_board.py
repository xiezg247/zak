"""首板人气评分与排序测试。"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from vnpy_ashare.quotes.radar.radar_first_board import (
    build_first_board_candidates,
    compute_first_board_score,
    format_seal_time_label,
    rank_first_board_pool,
    seal_time_score,
)


def _row(symbol: str, *, boards: int = 1, amount: float = 1e8, industry: str = "半导体") -> dict:
    return {
        "vt_symbol": f"{symbol}.SSE",
        "symbol": symbol,
        "name": symbol,
        "industry": industry,
        "limit_times": boards,
        "change_pct": 10.0,
        "amount": amount,
    }


class FirstBoardTest(unittest.TestCase):
    def test_seal_time_score_buckets(self) -> None:
        self.assertEqual(seal_time_score("09:35:00"), 1.0)
        self.assertEqual(seal_time_score("11:00:00"), 0.7)
        self.assertEqual(seal_time_score("14:20:00"), 0.5)
        self.assertEqual(seal_time_score(""), 0.0)

    def test_format_seal_time_label(self) -> None:
        self.assertEqual(format_seal_time_label("103015"), "10:30 封板")

    @patch("vnpy_ashare.quotes.radar.radar_limit_ladder.apply_recipe_filters", side_effect=lambda rows: rows)
    def test_build_first_board_candidates_only_first_board(self, _filters) -> None:
        rows = [_row("A", boards=1), _row("B", boards=3)]
        candidates = build_first_board_candidates(rows, limit_times_map={})
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["symbol"], "A")

    def test_compute_first_board_score_prefers_early_seal(self) -> None:
        early = compute_first_board_score(
            _row("A"),
            amount_rank=0.5,
            sector_bonus=0.0,
            seal_score=1.0,
        )
        late = compute_first_board_score(
            _row("A"),
            amount_rank=0.5,
            sector_bonus=0.0,
            seal_score=0.5,
        )
        self.assertGreater(early, late)

    @patch("vnpy_ashare.quotes.radar.radar_first_board._strong_industries", return_value=set())
    def test_rank_first_board_pool_orders_by_score(self, _strong) -> None:
        rows = [_row("low", amount=5e7), _row("high", amount=3e8)]
        ranked = rank_first_board_pool(
            rows,
            first_time_map={"low.SSE": "143000", "high.SSE": "093500"},
            top_n=2,
        )
        self.assertEqual(ranked[0][0]["symbol"], "high")
        self.assertIn("09:35", ranked[0][2])
