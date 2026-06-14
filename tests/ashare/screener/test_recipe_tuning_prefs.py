"""配方评分参数偏好测试。"""

from __future__ import annotations

from vnpy_ashare.screener.dimensions.scoring import metric_score_blend
from vnpy_ashare.screener.recipe_tuning_prefs import (
    RecipeTuningPrefs,
    load_recipe_tuning_prefs,
    save_recipe_tuning_prefs,
)
from vnpy_ashare.screener.sentiment.sentiment_gate import sentiment_gate_enabled


def test_save_and_load_recipe_tuning_prefs() -> None:
    save_recipe_tuning_prefs(
        RecipeTuningPrefs(
            metric_score_blend=0.7,
            momentum_min_change_pct=1.0,
            momentum_max_change_pct=8.0,
            momentum_fear_max_change_pct=6.0,
            sentiment_gate_enabled=False,
            extreme_fear_momentum=0.1,
            extreme_fear_sector=0.05,
            extreme_fear_breakout=0.04,
            fear_momentum=0.03,
            extreme_greed_turnover=0.05,
            extreme_greed_volume_surge=0.03,
            greed_turnover=0.02,
        )
    )
    prefs = load_recipe_tuning_prefs()
    assert prefs.metric_score_blend == 0.7
    assert prefs.momentum_min_change_pct == 1.0
    assert prefs.sentiment_gate_enabled is False
    assert metric_score_blend() == 0.7
    assert sentiment_gate_enabled() is False
