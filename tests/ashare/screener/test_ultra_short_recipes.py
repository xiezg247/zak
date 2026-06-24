"""极致短线 Recipe 与激进硬过滤测试。"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from vnpy_ashare.quotes.radar.radar_sector import _build_leaders_tiered_rows
from vnpy_ashare.screener.dimensions.limit_board import run_limit_board
from vnpy_ashare.screener.hard_filter_prefs import PRESET_AGGRESSIVE, hard_filter_preset
from vnpy_ashare.screener.recipe.recipe import (
    BUILTIN_RECIPES,
    RECIPE_CM20_ELASTIC,
    RECIPE_EMOTION_GATE_ONLY,
    RECIPE_ULTRA_SHORT_FIRST_BOARD,
    RECIPE_ULTRA_SHORT_LIMIT,
    list_recipe_catalog,
)
from vnpy_ashare.screener.sentiment.emotion_gate import apply_emotion_gate_only_finalize


class UltraShortRecipeTest(unittest.TestCase):
    def test_ultra_short_limit_recipe_dimensions(self) -> None:
        recipe = BUILTIN_RECIPES[RECIPE_ULTRA_SHORT_LIMIT]
        ids = {spec.dimension_id for spec in recipe.dimensions}
        self.assertIn("limit_board", ids)
        self.assertIn("sector_strength", ids)
        self.assertEqual(recipe.trigger_kind, "intraday")

    def test_ultra_short_first_board_recipe_dimensions(self) -> None:
        recipe = BUILTIN_RECIPES[RECIPE_ULTRA_SHORT_FIRST_BOARD]
        ids = {spec.dimension_id for spec in recipe.dimensions}
        self.assertIn("first_board", ids)
        self.assertIn("concept_strength", ids)

    def test_intraday_catalog_includes_ultra_short(self) -> None:
        ids = {entry.recipe_id for entry in list_recipe_catalog(trigger_kind="intraday")}
        self.assertIn(RECIPE_ULTRA_SHORT_LIMIT, ids)
        self.assertIn(RECIPE_ULTRA_SHORT_FIRST_BOARD, ids)
        self.assertIn(RECIPE_CM20_ELASTIC, ids)
        self.assertIn(RECIPE_EMOTION_GATE_ONLY, ids)

    def test_cm20_elastic_recipe_dimensions(self) -> None:
        recipe = BUILTIN_RECIPES[RECIPE_CM20_ELASTIC]
        ids = {spec.dimension_id for spec in recipe.dimensions}
        self.assertIn("cm20_elastic", ids)
        self.assertIn("concept_strength", ids)

    def test_emotion_gate_only_recipe(self) -> None:
        recipe = BUILTIN_RECIPES[RECIPE_EMOTION_GATE_ONLY]
        self.assertEqual(recipe.top_n, 3)
        self.assertIn("sentiment_gate", {spec.dimension_id for spec in recipe.dimensions})

    def test_emotion_gate_finalize_ice_returns_empty(self) -> None:
        from unittest.mock import MagicMock

        rows = [{"vt_symbol": "600000.SSE", "composite_score": 80.0, "hit_reason": "动量"}]
        cycle = MagicMock(stage="ice", stage_label="冰点", allow_new_positions=False)
        with patch("vnpy_ashare.screener.sentiment.emotion_gate.try_load_emotion_cycle_snapshot", return_value=cycle):
            result, meta = apply_emotion_gate_only_finalize(rows, top_n=3)
        self.assertEqual(result, [])
        self.assertIn("不宜新开", meta["gate_message"])

    def test_emotion_gate_finalize_recession_caps_three(self) -> None:
        from unittest.mock import MagicMock

        rows = [{"vt_symbol": f"60000{i}.SSE", "composite_score": 90 - i, "hit_reason": f"r{i}"} for i in range(5)]
        cycle = MagicMock(stage="recession", stage_label="退潮", allow_new_positions=False)
        with patch("vnpy_ashare.screener.sentiment.emotion_gate.try_load_emotion_cycle_snapshot", return_value=cycle):
            result, meta = apply_emotion_gate_only_finalize(rows, top_n=3)
        self.assertEqual(len(result), 3)
        self.assertIn("退潮观察", result[0]["hit_reason"])
        self.assertIn("Top3", meta["gate_message"])

    def test_aggressive_hard_filter_preset_values(self) -> None:
        prefs = hard_filter_preset(PRESET_AGGRESSIVE)
        self.assertEqual(prefs.min_amount_wan, 5000.0)
        self.assertEqual(prefs.min_total_mv_yi, 30.0)
        self.assertFalse(prefs.exclude_limit_board)

    @patch("vnpy_ashare.screener.dimensions.limit_board.build_limit_ladder_candidates")
    @patch("vnpy_ashare.screener.dimensions.limit_board.attach_industry", side_effect=lambda rows: rows)
    @patch("vnpy_ashare.screener.dimensions.limit_board.load_screening_quote_snapshot")
    @patch("vnpy_ashare.screener.dimensions.limit_board.get_cached_limit_times_map", return_value={})
    def test_run_limit_board_dimension(self, _limit_map, mock_snapshot, _industry, mock_pool) -> None:
        from types import SimpleNamespace

        mock_snapshot.return_value = SimpleNamespace(
            rows=[{"vt_symbol": "600000.SSE", "limit_times": 3, "change_pct": 10.0, "amount": 2e8}],
            total=100,
        )
        mock_pool.return_value = [
            {"vt_symbol": "600000.SSE", "limit_times": 3, "change_pct": 10.0, "amount": 2e8, "industry": "半导体"},
        ]
        hits, total = run_limit_board(5, weight=0.35)
        self.assertEqual(total, 100)
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].dimension_id, "limit_board")

    @patch("vnpy_ashare.screener.dimensions.cm20_elastic.apply_recipe_filters", side_effect=lambda rows: rows)
    @patch("vnpy_ashare.screener.dimensions.cm20_elastic.attach_industry", side_effect=lambda rows: rows)
    @patch("vnpy_ashare.screener.dimensions.cm20_elastic.load_screening_quote_snapshot")
    def test_run_cm20_elastic_dimension(self, mock_snapshot, _industry, _filters) -> None:
        from types import SimpleNamespace

        from vnpy_ashare.screener.dimensions.cm20_elastic import run_cm20_elastic

        mock_snapshot.return_value = SimpleNamespace(
            rows=[
                {
                    "vt_symbol": "300001.SZSE",
                    "symbol": "300001",
                    "change_pct": 12.0,
                    "amount": 2e8,
                    "total_mv": 500000,
                }
            ],
            total=100,
        )
        hits, total = run_cm20_elastic(5, weight=0.45)
        self.assertEqual(total, 100)
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].dimension_id, "cm20_elastic")

    @patch("vnpy_ashare.quotes.radar.radar_sector.run_sector_strength")
    @patch("vnpy_ashare.quotes.radar.radar_sector.rank_unified_sector_leaders")
    def test_leaders_tiered_limits_per_sector(self, mock_rank, mock_strength) -> None:
        from vnpy_ashare.quotes.radar.radar_leader import LeaderScoredRow

        row_a1 = {"vt_symbol": "A.SSE", "industry": "半导体", "change_pct": 10.0, "amount": 1e8}
        row_a2 = {"vt_symbol": "B.SSE", "industry": "半导体", "change_pct": 9.0, "amount": 9e7}
        row_c = {"vt_symbol": "C.SSE", "industry": "银行", "change_pct": 8.0, "amount": 8e7}
        mock_strength.return_value = ([], 500)
        mock_rank.return_value = [
            LeaderScoredRow(row=row_a1, leader_score=90.0, leader_tier="dragon_1", limit_times=3, sector_name="半导体"),
            LeaderScoredRow(row=row_a2, leader_score=80.0, leader_tier="dragon_2", limit_times=2, sector_name="半导体"),
            LeaderScoredRow(row=row_c, leader_score=75.0, leader_tier="dragon_1", limit_times=2, sector_name="银行"),
        ]
        rows, subtitle, total, sectors = _build_leaders_tiered_rows(8)
        symbols = [row.symbol for row in rows]
        self.assertEqual(symbols, ["A", "B", "C"])
        self.assertIn("分层", subtitle)
        self.assertEqual(sectors[0], "半导体")
