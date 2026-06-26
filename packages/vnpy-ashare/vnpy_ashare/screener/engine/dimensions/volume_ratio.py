"""Polars 量比维度。"""

from __future__ import annotations

from typing import Any

import polars as pl

from vnpy_ashare.domain.market.quote_row import QuoteRow
from vnpy_ashare.screener.dimensions.base import DimensionHit, quote_hits
from vnpy_ashare.screener.engine.snapshot_frame import frame_to_row_dicts, snapshot_rows_to_dataframe
from vnpy_ashare.screener.hard_filters import apply_recipe_filters
from vnpy_ashare.screener.preset.rules import _quote_row

_VOLUME_RATIO_TIER_2 = 2.0
_VOLUME_RATIO_TIER_5 = 5.0
_VOLUME_RATIO_BONUS_2 = 1.06
_VOLUME_RATIO_BONUS_5 = 1.12


def volume_ratio_tier_factor(ratio: float) -> float:
    if ratio >= _VOLUME_RATIO_TIER_5:
        return _VOLUME_RATIO_BONUS_5
    if ratio >= _VOLUME_RATIO_TIER_2:
        return _VOLUME_RATIO_BONUS_2
    return 1.0


def volume_ratio_reason(row: dict[str, Any], rank: int) -> str:
    ratio = float(row.get("volume_ratio") or 0)
    tier_note = ""
    if ratio >= _VOLUME_RATIO_TIER_5:
        tier_note = "（强放量）"
    elif ratio >= _VOLUME_RATIO_TIER_2:
        tier_note = "（放量）"
    return f"量比：{ratio:.2f}{tier_note}，排名第 {rank}"


def run_volume_ratio_polars(
    rows: list[Any],
    *,
    pool_size: int,
    weight: float,
    total: int,
) -> tuple[list[DimensionHit], int] | None:
    """向量化量比；无有效 ratio 时返回 None 供调用方降级 Tushare。"""
    from vnpy_ashare.screener.data.screening_context import get_volume_ratio_map

    ratio_map = get_volume_ratio_map()
    if not ratio_map:
        return None

    df = snapshot_rows_to_dataframe(rows)
    if df.is_empty():
        return None

    df = df.filter(pl.col("vt_symbol").cast(pl.Utf8, strict=False).fill_null("").str.len_chars() > 0)
    map_df = pl.DataFrame({"vt_symbol": list(ratio_map.keys()), "volume_ratio": list(ratio_map.values())})
    df = df.join(map_df, on="vt_symbol", how="inner")
    ratio = pl.col("volume_ratio").cast(pl.Float64, strict=False).fill_null(0.0)
    df = df.filter(ratio > 0).sort("volume_ratio", descending=True, nulls_last=True)
    if df.is_empty():
        return None

    filtered = apply_recipe_filters(frame_to_row_dicts(df))
    hit_rows: list[QuoteRow] = []
    for item in filtered[:pool_size]:
        base = _quote_row(item)
        base["volume_ratio"] = float(item.get("volume_ratio") or 0)
        hit_rows.append(base)

    return quote_hits(
        hit_rows,
        dimension_id="volume_ratio",
        label="量比",
        weight=weight,
        metric_key="volume_ratio",
        reason_builder=lambda row, rank: volume_ratio_reason(row, rank),
        score_adjustment=lambda row: volume_ratio_tier_factor(float(row.get("volume_ratio") or 0)),
    ), total
