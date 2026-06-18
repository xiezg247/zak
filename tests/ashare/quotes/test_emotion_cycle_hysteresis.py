"""情绪阶段 hysteresis 测试。"""

from __future__ import annotations

import unittest

from vnpy_ashare.config.preferences.emotion_cycle import EmotionCycleThresholds
from vnpy_ashare.quotes.market.emotion_cycle import classify_emotion_cycle
from vnpy_ashare.quotes.market.emotion_cycle_hysteresis import (
    apply_stage_hysteresis,
    reset_emotion_stage_hysteresis,
)
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


class EmotionCycleHysteresisTest(unittest.TestCase):
    def setUp(self) -> None:
        reset_emotion_stage_hysteresis()

    def tearDown(self) -> None:
        reset_emotion_stage_hysteresis()

    def test_startup_holds_when_limit_up_dips_below_enter_threshold(self) -> None:
        thresholds = EmotionCycleThresholds(startup_limit_up=50, hysteresis_enabled=True)
        enter = _inputs(limit_up_count=52, max_limit_times=4)
        snap_enter = classify_emotion_cycle(enter, thresholds=thresholds)
        self.assertEqual(snap_enter.stage, "startup")

        dip = _inputs(limit_up_count=48, max_limit_times=4)
        snap_dip = classify_emotion_cycle(dip, thresholds=thresholds)
        self.assertEqual(snap_dip.stage, "startup")

    def test_startup_releases_after_hold_band_exhausted(self) -> None:
        thresholds = EmotionCycleThresholds(startup_limit_up=50, hysteresis_enabled=True)
        classify_emotion_cycle(_inputs(limit_up_count=55, max_limit_times=4), thresholds=thresholds)
        snap = classify_emotion_cycle(_inputs(limit_up_count=40, max_limit_times=2), thresholds=thresholds)
        self.assertEqual(snap.stage, "divergence")

    def test_recession_overrides_hysteresis_immediately(self) -> None:
        thresholds = EmotionCycleThresholds(hysteresis_enabled=True)
        classify_emotion_cycle(_inputs(limit_up_count=90, limit_ladder_depth=3), thresholds=thresholds)
        snap = classify_emotion_cycle(_inputs(limit_down_count=25), thresholds=thresholds)
        self.assertEqual(snap.stage, "recession")

    def test_disabled_hysteresis_follows_raw_stage(self) -> None:
        thresholds = EmotionCycleThresholds(startup_limit_up=50, hysteresis_enabled=False)
        classify_emotion_cycle(_inputs(limit_up_count=55, max_limit_times=4), thresholds=thresholds)
        snap = classify_emotion_cycle(
            _inputs(limit_up_count=48, max_limit_times=2),
            thresholds=thresholds,
        )
        self.assertEqual(snap.stage, "divergence")

    def test_apply_stage_hysteresis_unit(self) -> None:
        thresholds = EmotionCycleThresholds(startup_limit_up=50)
        reset_emotion_stage_hysteresis()
        stable = apply_stage_hysteresis("startup", _inputs(limit_up_count=55, max_limit_times=4), thresholds)
        self.assertEqual(stable, "startup")
        held = apply_stage_hysteresis("divergence", _inputs(limit_up_count=48, max_limit_times=4), thresholds)
        self.assertEqual(held, "startup")


if __name__ == "__main__":
    unittest.main()
