"""情绪周期引擎测试。"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from vnpy_ashare.quotes.market.emotion_cycle import (
    classify_emotion_cycle,
    invalidate_emotion_cycle_cache,
    load_emotion_cycle_snapshot,
)
from vnpy_ashare.quotes.market.emotion_cycle_inputs import EmotionCycleInputs, compute_limit_ladder_stats


def _inputs(**kwargs) -> EmotionCycleInputs:
    defaults = dict(
        limit_up_count=40,
        limit_down_count=5,
        up_ratio=0.45,
        total_amount=2e12,
        max_limit_times=2,
        limit_ladder_depth=0,
        index_above_ma5=None,
        fear_greed_index=None,
        updated_at="2026-06-17 10:00",
    )
    defaults.update(kwargs)
    return EmotionCycleInputs(**defaults)


class EmotionCycleEngineTest(unittest.TestCase):
    def test_recession_blocks_new_positions(self) -> None:
        snap = classify_emotion_cycle(_inputs(limit_down_count=25))
        self.assertEqual(snap.stage, "recession")
        self.assertFalse(snap.allow_new_positions)

    def test_ice_when_low_boards_and_weak_breadth(self) -> None:
        snap = classify_emotion_cycle(
            _inputs(max_limit_times=2, limit_down_count=18, up_ratio=0.30, limit_up_count=20),
        )
        self.assertEqual(snap.stage, "ice")

    def test_climax_requires_ladder_and_limit_up(self) -> None:
        snap = classify_emotion_cycle(
            _inputs(limit_up_count=90, limit_ladder_depth=3, max_limit_times=5),
        )
        self.assertEqual(snap.stage, "climax")
        self.assertGreaterEqual(snap.position_factor, 0.6)

    def test_low_amount_reduces_factor(self) -> None:
        high = classify_emotion_cycle(_inputs(limit_up_count=90, limit_ladder_depth=3, total_amount=2e12))
        low = classify_emotion_cycle(_inputs(limit_up_count=90, limit_ladder_depth=3, total_amount=8e11))
        self.assertLess(low.position_factor, high.position_factor)

    def test_index_below_ma5_removes_limit_board(self) -> None:
        snap = classify_emotion_cycle(
            _inputs(limit_up_count=55, max_limit_times=4, index_above_ma5=False),
        )
        self.assertEqual(snap.stage, "startup")
        self.assertNotIn("limit_board", snap.allowed_modes)

    def test_limit_ladder_depth(self) -> None:
        max_boards, depth = compute_limit_ladder_stats({"a": 2, "b": 3, "c": 5})
        self.assertEqual(max_boards, 5)
        self.assertEqual(depth, 3)

    def test_to_dict_includes_inputs(self) -> None:
        snap = classify_emotion_cycle(_inputs())
        payload = snap.model_dump()
        self.assertIn("inputs", payload)
        self.assertIn("limit_up_count", payload["inputs"])

    def test_load_without_fetch_skips_network_when_no_cache(self) -> None:
        invalidate_emotion_cycle_cache()
        with (
            patch("vnpy_ashare.quotes.core.quote_rows.get_market_quotes_cache", return_value=[]),
            patch(
                "vnpy_ashare.screener.data.quotes_loader.load_market_quote_rows",
                side_effect=AssertionError("should not fetch"),
            ),
        ):
            self.assertIsNone(load_emotion_cycle_snapshot(fetch_if_missing=False))
