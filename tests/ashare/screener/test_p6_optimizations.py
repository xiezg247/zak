"""P6 集成收尾测试。"""

from __future__ import annotations

from unittest.mock import patch

from vnpy_ashare.screener.dimensions.base import DimensionHit
from vnpy_ashare.screener.dimensions.volume_dedup import (
    apply_volume_liquidity_dedup,
    build_volume_discovery_subtitle,
)
from vnpy_ashare.screener.recipe.recipe import BUILTIN_RECIPES, RECIPE_INTRADAY_AGGRESSIVE, RECIPE_INTRADAY_MULTI


def test_intraday_multi_includes_concept_strength() -> None:
    recipe = BUILTIN_RECIPES[RECIPE_INTRADAY_MULTI]
    ids = {spec.dimension_id for spec in recipe.dimensions}
    assert "concept_strength" in ids


def test_intraday_aggressive_recipe_exists() -> None:
    recipe = BUILTIN_RECIPES[RECIPE_INTRADAY_AGGRESSIVE]
    ids = {spec.dimension_id for spec in recipe.dimensions}
    assert "intraday_breakout" in ids
    assert "moneyflow_intraday" in ids
    assert recipe.min_dimensions >= 3


def test_volume_liquidity_dedup_weakens_surge() -> None:
    hits = [
        DimensionHit("600000.SSE", "volume_ratio", "量比", 0.25, 80.0, "量比", {}),
        DimensionHit("600000.SSE", "volume_surge", "放量", 0.1, 70.0, "放量", {}),
    ]
    with patch(
        "vnpy_ashare.screener.dimensions.volume_dedup.volume_liquidity_dedup_factor",
        return_value=0.5,
    ):
        adjusted = apply_volume_liquidity_dedup(hits)
    surge = next(hit for hit in adjusted if hit.dimension_id == "volume_surge")
    assert surge.score == 35.0


def test_build_volume_discovery_subtitle_ratio() -> None:
    hits = [DimensionHit("600000.SSE", "volume_ratio", "量比", 1.0, 80.0, "量比", {})]
    assert "量比排序" in build_volume_discovery_subtitle(hits)
