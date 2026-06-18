"""情绪周期阈值偏好测试。"""

from __future__ import annotations

import unittest

from vnpy_ashare.config.preferences.emotion_cycle import (
    DEFAULT_EMOTION_CYCLE_THRESHOLDS,
    EmotionCycleThresholds,
    load_emotion_cycle_thresholds,
    reset_emotion_cycle_thresholds,
    save_emotion_cycle_thresholds,
)
from vnpy_ashare.quotes.market.emotion_cycle import classify_emotion_cycle
from vnpy_ashare.quotes.market.emotion_cycle_inputs import EmotionCycleInputs


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


class EmotionCycleThresholdsTest(unittest.TestCase):
    def setUp(self) -> None:
        reset_emotion_cycle_thresholds()

    def tearDown(self) -> None:
        reset_emotion_cycle_thresholds()

    def test_custom_recession_threshold(self) -> None:
        custom = DEFAULT_EMOTION_CYCLE_THRESHOLDS.model_copy(update={"recession_limit_down": 30})
        snap_default = classify_emotion_cycle(_inputs(limit_down_count=25), thresholds=DEFAULT_EMOTION_CYCLE_THRESHOLDS)
        snap_custom = classify_emotion_cycle(_inputs(limit_down_count=25), thresholds=custom)
        self.assertEqual(snap_default.stage, "recession")
        self.assertNotEqual(snap_custom.stage, "recession")

    def test_save_and_load_roundtrip(self) -> None:
        custom = DEFAULT_EMOTION_CYCLE_THRESHOLDS.model_copy(update={"startup_limit_up": 60})
        save_emotion_cycle_thresholds(custom)
        loaded = load_emotion_cycle_thresholds()
        self.assertEqual(loaded.startup_limit_up, 60)

    def test_reset_restores_defaults(self) -> None:
        save_emotion_cycle_thresholds(
            EmotionCycleThresholds.model_validate(
                {**DEFAULT_EMOTION_CYCLE_THRESHOLDS.model_dump(), "climax_limit_up": 99},
            ),
        )
        reset_emotion_cycle_thresholds()
        self.assertEqual(load_emotion_cycle_thresholds(), DEFAULT_EMOTION_CYCLE_THRESHOLDS)


if __name__ == "__main__":
    unittest.main()
