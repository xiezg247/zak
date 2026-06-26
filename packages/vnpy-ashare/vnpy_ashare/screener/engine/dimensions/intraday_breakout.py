"""Polars 盘中突破候选评分（K 线 / 分钟确认仍走 Python）。"""

from __future__ import annotations

from typing import Any

import polars as pl

from vnpy_ashare.domain.market.quote_row import QuoteRow, coerce_quote_row
from vnpy_ashare.screener.data.screening_context import get_volume_ratio_map
from vnpy_ashare.screener.dimensions.intraday_breakout import (
    _MAX_PULLBACK_FROM_HIGH_PCT,
    _MIN_BREAKOUT_VOLUME_RATIO,
    _MIN_BREAK_PCT,
    _MIN_CHANGE_PCT,
    _NEAR_HIGH_RATIO,
)
from vnpy_ashare.screener.engine.snapshot_frame import change_pct_expr, frame_to_row_dicts, snapshot_rows_to_dataframe


def score_breakout_candidates_polars(rows: list[Any]) -> list[tuple[QuoteRow, float]]:
    ratio_map = get_volume_ratio_map()
    df = snapshot_rows_to_dataframe(rows)
    if df.is_empty():
        return []

    if ratio_map:
        map_df = pl.DataFrame({"vt_symbol": list(ratio_map.keys()), "_map_ratio": list(ratio_map.values())})
        df = df.join(map_df, on="vt_symbol", how="left")
    else:
        df = df.with_columns(pl.lit(None).cast(pl.Float64).alias("_map_ratio"))

    prev = pl.col("prev_close").cast(pl.Float64, strict=False).fill_null(0.0)
    high = pl.coalesce(
        pl.col("high_price").cast(pl.Float64, strict=False),
        pl.col("high").cast(pl.Float64, strict=False),
    ).fill_null(0.0)
    last = pl.coalesce(
        pl.col("last_price").cast(pl.Float64, strict=False),
        pl.col("close").cast(pl.Float64, strict=False),
    ).fill_null(0.0)
    change = change_pct_expr()
    row_ratio = pl.col("volume_ratio").cast(pl.Float64, strict=False).fill_null(0.0)
    map_ratio = pl.col("_map_ratio").cast(pl.Float64, strict=False).fill_null(0.0)
    volume_ratio = pl.max_horizontal(row_ratio, map_ratio)
    has_ratio = volume_ratio > 0

    df = df.with_columns(
        pl.when((prev > 0) & (high > 0) & (last > 0)).then((last - prev) / prev * 100.0).otherwise(None).alias("_strength"),
        pl.when(high > 0).then((high - last) / high * 100.0).otherwise(pl.lit(999.0)).alias("_pullback_pct"),
        volume_ratio.alias("_volume_ratio"),
        has_ratio.alias("_has_ratio"),
        change.alias("_change"),
        prev.alias("_prev"),
        high.alias("_high"),
        last.alias("_last"),
    )
    df = df.filter(
        (pl.col("_prev") > 0)
        & (pl.col("_high") > 0)
        & (pl.col("_last") > 0)
        & (pl.col("_change") >= _MIN_CHANGE_PCT)
        & (pl.col("_high") >= pl.col("_prev") * (1.0 + _MIN_BREAK_PCT / 100.0))
        & (pl.col("_last") >= pl.col("_high") * _NEAR_HIGH_RATIO)
        & (pl.col("_pullback_pct") <= _MAX_PULLBACK_FROM_HIGH_PCT)
        & (~pl.col("_has_ratio") | (pl.col("_volume_ratio") >= _MIN_BREAKOUT_VOLUME_RATIO))
        & pl.col("_strength").is_not_null()
    ).sort("_strength", descending=True, nulls_last=True)

    scored: list[tuple[QuoteRow, float]] = []
    for item in frame_to_row_dicts(df):
        strength = float(item.get("_strength") or 0)
        if strength <= 0:
            continue
        scored.append((coerce_quote_row(item), strength))
    return scored
