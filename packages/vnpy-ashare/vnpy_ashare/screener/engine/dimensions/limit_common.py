"""Polars 连板/首板候选池共用过滤。"""

from __future__ import annotations

from typing import Any

import polars as pl

from vnpy_ashare.quotes.core.enrich import get_cached_limit_times_map
from vnpy_ashare.screener.data.screening_context import get_stock_industry_l1_map, get_stock_industry_map
from vnpy_ashare.screener.engine.hard_filter import _change_pct_expr, _limit_threshold_expr, _symbol_expr
from vnpy_ashare.screener.engine.snapshot_frame import attach_industry_columns, frame_to_row_dicts, snapshot_rows_to_dataframe
from vnpy_ashare.screener.hard_filters import apply_recipe_filters


def collect_limit_candidate_rows(
    rows: list[Any],
    *,
    min_boards: float = 1.0,
    max_boards: float | None = None,
    apply_recipe: bool = True,
) -> list[dict[str, Any]]:
    """Polars 粗筛连板池 → dict 行（精排仍走 resolve_limit_times）。"""
    limit_map = get_cached_limit_times_map()
    industry_map = get_stock_industry_map()
    industry_l1_map = get_stock_industry_l1_map()
    df = snapshot_rows_to_dataframe(rows)
    if df.is_empty():
        return []

    df = attach_industry_columns(
        df,
        industry_map=industry_map,
        industry_l1_map=industry_l1_map,
        drop_unmapped=True,
    )
    if df.is_empty():
        return []

    symbol = _symbol_expr()
    change = _change_pct_expr()
    df = df.with_columns(
        symbol.alias("_symbol"),
        change.alias("_change_pct"),
        pl.col("vt_symbol").cast(pl.Utf8, strict=False).fill_null("").alias("_vt_symbol"),
        pl.col("vt_symbol").cast(pl.Utf8, strict=False).fill_null("").str.split(".").list.first().alias("_tf_key"),
    )
    if limit_map:
        map_df = pl.DataFrame({"_tf_key": list(limit_map.keys()), "_map_limit": list(limit_map.values())})
        df = df.join(map_df, on="_tf_key", how="left")
    else:
        df = df.with_columns(pl.lit(None).cast(pl.Float64).alias("_map_limit"))

    row_limit = pl.col("limit_times").cast(pl.Float64, strict=False).fill_null(0.0)
    map_limit = pl.col("_map_limit").cast(pl.Float64, strict=False).fill_null(0.0)
    threshold = _limit_threshold_expr(pl.lit(""), symbol)
    at_limit = (change >= threshold) | (change <= -threshold)
    boards = pl.max_horizontal(row_limit, map_limit, pl.when(at_limit).then(1.0).otherwise(0.0))

    df = df.filter(boards >= min_boards).with_columns(boards.alias("limit_times"))
    if max_boards is not None:
        df = df.filter(pl.col("limit_times") <= max_boards)
    if df.is_empty():
        return []

    row_dicts = frame_to_row_dicts(df)
    if apply_recipe:
        return apply_recipe_filters(row_dicts)
    return row_dicts
