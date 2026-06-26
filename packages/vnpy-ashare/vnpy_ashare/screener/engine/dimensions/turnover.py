"""Polars 换手维度。"""

from __future__ import annotations

from typing import Any

import polars as pl

from vnpy_ashare.domain.market.quote_row import QuoteRow
from vnpy_ashare.screener.data.screening_context import get_avg_turnover_map
from vnpy_ashare.screener.dimensions.base import DimensionHit, quote_hits
from vnpy_ashare.screener.engine.snapshot_frame import frame_to_row_dicts, snapshot_rows_to_dataframe
from vnpy_ashare.screener.hard_filters import apply_recipe_filters
from vnpy_ashare.screener.preset.rules import _quote_row


def _turnover_reason(row: dict[str, Any], rank: int) -> str:
    turnover = float(row.get("turnover_rate") or 0)
    relative = float(row.get("relative_turnover") or 0)
    avg_turnover = float(row.get("avg_turnover_rate") or 0)
    if avg_turnover > 0:
        return f"换手：{turnover:.2f}%（均 {avg_turnover:.2f}%），相对 {relative:.2f}，排名第 {rank}"
    return f"换手：{turnover:.2f}%，排名第 {rank}"


def run_turnover_polars(
    rows: list[Any],
    *,
    pool_size: int,
    weight: float,
    total: int,
) -> tuple[list[DimensionHit], int]:
    avg_map = get_avg_turnover_map()
    df = snapshot_rows_to_dataframe(rows)
    if df.is_empty():
        return [], total

    df = df.filter(pl.col("vt_symbol").cast(pl.Utf8, strict=False).fill_null("").str.len_chars() > 0)
    turnover = pl.col("turnover_rate").cast(pl.Float64, strict=False).fill_null(0.0)
    df = df.filter(turnover > 0)

    if avg_map:
        map_df = pl.DataFrame(
            {"vt_symbol": list(avg_map.keys()), "avg_turnover_rate": list(avg_map.values())},
        )
        df = df.join(map_df, on="vt_symbol", how="left")
    else:
        df = df.with_columns(pl.lit(None).cast(pl.Float64).alias("avg_turnover_rate"))

    avg_col = pl.col("avg_turnover_rate").cast(pl.Float64, strict=False).fill_null(0.0)
    df = df.with_columns(
        avg_col.alias("avg_turnover_rate"),
        pl.when(avg_col > 0)
        .then(turnover / avg_col)
        .when(turnover > 0)
        .then(turnover)
        .otherwise(pl.lit(0.0))
        .alias("relative_turnover"),
    )
    df = df.sort("relative_turnover", descending=True, nulls_last=True)

    filtered = apply_recipe_filters(frame_to_row_dicts(df))
    hit_rows: list[QuoteRow] = []
    for item in filtered[:pool_size]:
        base = _quote_row(item)
        base["avg_turnover_rate"] = float(item.get("avg_turnover_rate") or 0)
        base["relative_turnover"] = float(item.get("relative_turnover") or 0)
        hit_rows.append(base)

    return quote_hits(
        hit_rows,
        dimension_id="turnover",
        label="换手",
        weight=weight,
        metric_key="relative_turnover",
        reason_builder=_turnover_reason,
    ), total
