"""Polars 放量维度。"""

from __future__ import annotations

from typing import Any

import polars as pl

from vnpy_ashare.domain.market.quote_row import QuoteRow
from vnpy_ashare.screener.data.screening_context import get_volume_ratio_map
from vnpy_ashare.screener.dimensions.base import DimensionHit, quote_hits
from vnpy_ashare.screener.dimensions.volume_surge import _volume_surge_reason
from vnpy_ashare.screener.engine.snapshot_frame import frame_to_row_dicts, snapshot_rows_to_dataframe
from vnpy_ashare.screener.hard_filters import apply_recipe_filters
from vnpy_ashare.screener.preset.rules import _quote_row


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

    row_ratio = pl.col("volume_ratio").cast(pl.Float64, strict=False).fill_null(0.0)
    map_ratio = pl.col("_map_ratio").cast(pl.Float64, strict=False).fill_null(0.0)
    ratio = pl.max_horizontal(map_ratio, row_ratio)
    volume = pl.col("volume").cast(pl.Float64, strict=False).fill_null(0.0)
    amount = pl.col("amount").cast(pl.Float64, strict=False).fill_null(0.0)

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
        base = _quote_row(item)
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
