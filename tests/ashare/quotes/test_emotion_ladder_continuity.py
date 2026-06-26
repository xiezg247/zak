"""连板日切与断板率测试。"""

from __future__ import annotations

import unittest

from vnpy_ashare.config.preferences.emotion_cycle import DEFAULT_EMOTION_CYCLE_THRESHOLDS
from vnpy_ashare.quotes.market.emotion_cycle import classify_emotion_cycle
from vnpy_ashare.quotes.market.emotion_cycle_inputs import EmotionCycleInputs
from vnpy_ashare.quotes.market.emotion_ladder_continuity import (
    build_ladder_snapshot_from_map,
    compute_ladder_continuity,
    is_limit_down_change,
)
from vnpy_ashare.storage.connection import connect
from vnpy_ashare.storage.repositories.emotion_ladder_daily import (
    load_ladder_snapshot,
    save_ladder_snapshot,
)


class EmotionLadderContinuityTest(unittest.TestCase):
    def setUp(self) -> None:
        with connect() as conn:
            conn.execute("DELETE FROM emotion_limit_ladder_daily")
            conn.execute("DELETE FROM meta WHERE key LIKE 'emotion_ladder_counts:%'")

    def test_build_snapshot_from_tickflow_map(self) -> None:
        snapshot = build_ladder_snapshot_from_map(
            {"600519.SH": 3.0, "000001.SZ": 2.0, "300750.SZ": 1.0},
            trade_date="2026-06-17",
        )
        self.assertIsNotNone(snapshot)
        assert snapshot is not None
        self.assertEqual(snapshot.max_limit_times, 3)
        self.assertIn("600519.SSE", snapshot.linked_board_vt_symbols)

    def test_break_rate_triggers_recession(self) -> None:
        save_ladder_snapshot(
            build_ladder_snapshot_from_map(
                {"600519.SH": 3.0, "000001.SZ": 2.0},
                trade_date="2026-06-17",
            ),
        )
        prev = load_ladder_snapshot("2026-06-17")
        self.assertIsNotNone(prev)
        break_rate, leader_down, _ = compute_ladder_continuity(
            trade_date="2026-06-18",
            limit_times_map={},
            quote_change_by_vt={
                "600519.SSE": -10.0,
                "000001.SZSE": -10.0,
            },
        )
        self.assertIsNotNone(break_rate)
        assert break_rate is not None
        self.assertGreaterEqual(break_rate, 0.5)
        snap = classify_emotion_cycle(
            EmotionCycleInputs(
                limit_up_count=40,
                limit_down_count=5,
                up_ratio=0.45,
                total_amount=2e12,
                max_limit_times=2,
                limit_ladder_depth=1,
                limit_break_rate=break_rate,
                prev_leader_limit_down=leader_down,
            ),
            thresholds=DEFAULT_EMOTION_CYCLE_THRESHOLDS,
        )
        self.assertEqual(snap.stage, "recession")

    def test_limit_down_threshold_cm20(self) -> None:
        self.assertTrue(is_limit_down_change("300750.SZSE", -20.0))


if __name__ == "__main__":
    unittest.main()
