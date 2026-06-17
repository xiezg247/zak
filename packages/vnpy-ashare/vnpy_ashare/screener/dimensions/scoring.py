"""维度得分：排名分与指标分位数混合。"""

from __future__ import annotations

from vnpy_ashare.config.constants.recipe import (
    DEFAULT_METRIC_SCORE_BLEND,
    ENV_METRIC_SCORE_BLEND,
)
from vnpy_ashare.domain.env import env_or_prefs_float
from vnpy_ashare.screener.recipe_tuning_prefs import load_recipe_tuning_prefs


def metric_score_blend() -> float:
    return env_or_prefs_float(
        ENV_METRIC_SCORE_BLEND,
        default=DEFAULT_METRIC_SCORE_BLEND,
        prefs=lambda: load_recipe_tuning_prefs().metric_score_blend,
        clamp=(0.0, 1.0),
    )


def rank_score(rank: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round(max(0.0, (total - rank + 1) / total * 100), 1)


def metric_percentile(value: float, values: list[float]) -> float:
    """值越大分位数越高（截面百分位，0–100）。"""
    if not values:
        return 0.0
    count = sum(1 for item in values if item <= value)
    return round(count / len(values) * 100, 1)


def blended_score(
    rank: int,
    total: int,
    metric_value: float,
    metric_values: list[float],
    *,
    blend: float | None = None,
) -> float:
    """排名分与指标分位数加权；blend 默认读 RECIPE_METRIC_SCORE_BLEND。"""
    rank_part = rank_score(rank, total)
    if not metric_values:
        return rank_part
    weight = blend if blend is not None else metric_score_blend()
    metric_part = metric_percentile(metric_value, metric_values)
    return round(rank_part * (1.0 - weight) + metric_part * weight, 1)


def relative_ratio(current: float, baseline: float) -> float:
    if current <= 0:
        return 0.0
    if baseline <= 0:
        return current
    return current / baseline
