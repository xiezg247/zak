"""退潮期批量入自选软拦截测试。"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from vnpy_ashare.screener.sentiment.recession_watchlist_guard import is_emotion_recession


class TestRecessionWatchlistGuard(unittest.TestCase):
    def test_not_recession_when_snapshot_missing(self) -> None:
        with patch(
            "vnpy_ashare.quotes.market.emotion_cycle.load_emotion_cycle_snapshot",
            return_value=None,
        ):
            self.assertFalse(is_emotion_recession())

    def test_recession_stage_detected(self) -> None:
        from vnpy_ashare.quotes.market.emotion_cycle import EmotionCycleSnapshot

        snapshot = EmotionCycleSnapshot(
            stage="recession",
            stage_label="退潮",
            position_pct_min=0.0,
            position_pct_max=0.0,
            position_factor=0.0,
            allowed_modes=(),
            allow_new_positions=False,
            warnings=(),
            inputs={},
            updated_at="2026-06-17",
        )
        with patch(
            "vnpy_ashare.quotes.market.emotion_cycle.load_emotion_cycle_snapshot",
            return_value=snapshot,
        ):
            self.assertTrue(is_emotion_recession())

    def test_startup_not_recession(self) -> None:
        from vnpy_ashare.quotes.market.emotion_cycle import EmotionCycleSnapshot

        snapshot = EmotionCycleSnapshot(
            stage="startup",
            stage_label="启动",
            position_pct_min=0.3,
            position_pct_max=0.5,
            position_factor=0.4,
            allowed_modes=("limit_board",),
            allow_new_positions=True,
            warnings=(),
            inputs={},
            updated_at="2026-06-17",
        )
        with patch(
            "vnpy_ashare.quotes.market.emotion_cycle.load_emotion_cycle_snapshot",
            return_value=snapshot,
        ):
            self.assertFalse(is_emotion_recession())
