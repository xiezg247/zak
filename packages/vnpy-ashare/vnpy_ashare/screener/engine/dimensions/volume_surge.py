"""Polars 放量维度。"""

from __future__ import annotations

from typing import Any

import polars as pl

from vnpy_ashare.domain.market.quote_row import QuoteRow
from vnpy_ashare.screener.data.screening_factor_maps import get_volume_ratio_map
from vnpy_ashare.domain.screener.dimension_hit import DimensionHit
from vnpy_ashare.screener.engine.dimensions.hits import quote_hits, run_with_quote_snapshot
from vnpy_ashare.screener.engine.snapshot_frame import frame_to_row_dicts, snapshot_rows_to_dataframe
from vnpy_ashare.screener.hard_filters import apply_recipe_filters
from vnpy_ashare.screener.engine.row_normalize import normalize_quote_row


def _volume_surge_reason(row: dict[str, Any], rank: int) -> str:
    ratio = float(row.get("volume_ratio") or 0)
    relative = float(row.get("relative_volume") or 0)
    if ratio > 0:
        return f"放量：量比 {ratio:.2f}，相对量 {relative:.2f}，排名第 {rank}"
    volume = float(row.get("volume") or 0)
    if volume > 0:
        return f"放量：成交量 {volume:,.0f}，排名第 {rank}"
    amount = float(row.get("amount") or 0)
    return f"放量：成交额 {amount:,.0f}，排名第 {rank}"


def run_volume_surge_polars(
    rows: list[Any],
    *,
    pool_size: int,
    weight: float,
    total: int,
) -> tuple[list[DimensionHit], int]:
    ratio_map = get_volume_ratio_map()
    df = snapshot_rows_to_dataframe(rows)
    if df.is_empty():
        return [], total

    df = df.filter(pl.col("vt_symbol").cast(pl.Utf8, strict=False).fill_null("").str.len_chars() > 0)
    if ratio_map:
        map_df = pl.DataFrame({"vt_symbol": list(ratio_map.keys()), "_map_ratio": list(ratio_map.values())})
        df = df.join(map_df, on="vt_symbol", how="left")
    else:
        df = df.with_columns(pl.lit(None).cast(pl.Float64).alias("_map_ratio"))

    row_ratio = (
        pl.col("volume_ratio").cast(pl.Float64, strict=False).fill_null(0.0)
        if "volume_ratio" in df.columns
        else pl.lit(0.0)
    )
    map_ratio = pl.col("_map_ratio").cast(pl.Float64, strict=False).fill_null(0.0)
    ratio = pl.max_horizontal(map_ratio, row_ratio)
    volume = pl.col("volume").cast(pl.Float64, strict=False).fill_null(0.0) if "volume" in df.columns else pl.lit(0.0)
    amount = pl.col("amount").cast(pl.Float64, strict=False).fill_null(0.0) if "amount" in df.columns else pl.lit(0.0)

    df = df.with_columns(
        pl.when(ratio > 0).then(ratio).alias("volume_ratio"),
        pl.when(ratio > 0).then(ratio).when(volume > 0).then(volume).when(amount > 0).then(amount).otherwise(pl.lit(0.0)).alias("relative_volume"),
    )
    df = df.filter(pl.col("relative_volume") > 0).sort("relative_volume", descending=True, nulls_last=True)
    if df.is_empty():
        return [], total

    filtered = apply_recipe_filters(frame_to_row_dicts(df))
    hit_rows: list[QuoteRow] = []
    for item in filtered[:pool_size]:
        base = normalize_quote_row(item)
        base["volume_ratio"] = float(item.get("volume_ratio") or 0)
        base["relative_volume"] = float(item.get("relative_volume") or 0)
        hit_rows.append(base)

    return quote_hits(
        hit_rows,
        dimension_id="volume_surge",
        label="放量",
        weight=weight,
        metric_key="relative_volume",
        reason_builder=_volume_surge_reason,
    ), total

def run_volume_surge(pool_size: int, *, weight: float) -> tuple[list[DimensionHit], int]:
    return run_with_quote_snapshot(pool_size, weight=weight, runner=run_volume_surge_polars)
