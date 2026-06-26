"""配方评分 / 动量 / 恐贪调制参数；环境变量仍可覆盖。"""

from __future__ import annotations

from pydantic import Field

from vnpy_ashare.config.constants.recipe import DEFAULT_METRIC_SCORE_BLEND
from vnpy_ashare.storage.auth.preferences import get_pref, set_pref
from vnpy_common.domain.base import FrozenModel

_PREF_NAMESPACE = "screener"
_PREF_KEY = "recipe_tuning"


class RecipeTuningPrefs(FrozenModel):
    metric_score_blend: float = Field(description="指标评分混合权重")
    momentum_min_change_pct: float = Field(description="动量维度最低涨幅（%）")
    momentum_max_change_pct: float = Field(description="动量维度最高涨幅（%）")
    momentum_fear_max_change_pct: float = Field(description="恐慌期动量最高涨幅（%）")
    sentiment_gate_enabled: bool = Field(description="是否启用情绪门控")
    extreme_fear_momentum: float = Field(description="极度恐慌时动量权重衰减")
    extreme_fear_sector: float = Field(description="极度恐慌时板块权重衰减")
    extreme_fear_breakout: float = Field(description="极度恐慌时突破权重衰减")
    fear_momentum: float = Field(description="恐慌时动量权重衰减")
    extreme_greed_turnover: float = Field(description="极度贪婪时换手权重衰减")
    extreme_greed_volume_surge: float = Field(description="极度贪婪时放量权重衰减")
    greed_turnover: float = Field(description="贪婪时换手权重衰减")
    breakout_lookback_days: int = Field(description="突破回看天数")
    volume_liquidity_dedup_factor: float = Field(description="放量与流动性去重系数")


def default_recipe_tuning_prefs() -> RecipeTuningPrefs:
    return RecipeTuningPrefs(
        metric_score_blend=DEFAULT_METRIC_SCORE_BLEND,
        momentum_min_change_pct=0.5,
        momentum_max_change_pct=9.5,
        momentum_fear_max_change_pct=7.0,
        sentiment_gate_enabled=True,
        extreme_fear_momentum=0.08,
        extreme_fear_sector=0.05,
        extreme_fear_breakout=0.04,
        fear_momentum=0.04,
        extreme_greed_turnover=0.05,
        extreme_greed_volume_surge=0.03,
        greed_turnover=0.02,
        breakout_lookback_days=5,
        volume_liquidity_dedup_factor=0.5,
    )


def load_recipe_tuning_prefs() -> RecipeTuningPrefs:
    stored = get_pref(_PREF_NAMESPACE, _PREF_KEY, None)
    if stored is not None:
        return RecipeTuningPrefs.model_validate(stored)
    return default_recipe_tuning_prefs()


def save_recipe_tuning_prefs(prefs: RecipeTuningPrefs) -> None:
    set_pref(_PREF_NAMESPACE, _PREF_KEY, prefs.model_dump())
