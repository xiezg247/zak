"""量比 / 放量维度去重（避免流动性双计）。"""

from __future__ import annotations

from vnpy_ashare.config.constants.recipe import (
    DEFAULT_VOLUME_LIQUIDITY_DEDUP_FACTOR,
    ENV_VOLUME_LIQUIDITY_DEDUP_FACTOR,
)
from vnpy_ashare.domain.env import env_or_prefs_float
from vnpy_ashare.screener.dimensions.base import DimensionHit
from vnpy_ashare.screener.recipe_tuning_prefs import load_recipe_tuning_prefs

_VOLUME_LIQUIDITY_IDS = frozenset({"volume_ratio", "volume_surge"})


def build_volume_discovery_subtitle(hits: list[DimensionHit]) -> str:
    """发现·放量卡副标题：标注量比 / 相对放量 / 流动性代理。"""
    if not hits:
        return ""
    first = hits[0]
    if first.dimension_id == "volume_ratio":
        return " · 量比排序"
    if any(hit.row.get("moneyflow_proxy") or "代理" in hit.reason for hit in hits):
        return " · 流动性代理"
    return " · 相对放量"


def volume_liquidity_dedup_factor() -> float:
    return env_or_prefs_float(
        ENV_VOLUME_LIQUIDITY_DEDUP_FACTOR,
        default=DEFAULT_VOLUME_LIQUIDITY_DEDUP_FACTOR,
        prefs=lambda: load_recipe_tuning_prefs().volume_liquidity_dedup_factor,
        clamp=(0.0, 1.0),
    )


def apply_volume_liquidity_dedup(hits: list[DimensionHit]) -> list[DimensionHit]:
    """同票同时命中量比与放量时，削弱放量维度得分。"""
    dimension_ids = {hit.dimension_id for hit in hits}
    if not _VOLUME_LIQUIDITY_IDS.issubset(dimension_ids):
        return hits
    factor = volume_liquidity_dedup_factor()
    if factor >= 1.0:
        return hits
    adjusted: list[DimensionHit] = []
    for hit in hits:
        if hit.dimension_id != "volume_surge":
            adjusted.append(hit)
            continue
        adjusted.append(
            DimensionHit(
                vt_symbol=hit.vt_symbol,
                dimension_id=hit.dimension_id,
                label=hit.label,
                weight=hit.weight,
                score=round(hit.score * factor, 1),
                reason=hit.reason,
                row=hit.row,
            )
        )
    return adjusted
