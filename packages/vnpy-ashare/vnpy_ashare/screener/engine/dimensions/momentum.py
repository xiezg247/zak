"""Polars 动量维度（评分 / 过滤 / 排序；历史 persistence 仍走 Python K 线）。"""

from __future__ import annotations

from typing import Any

import polars as pl

from vnpy_ashare.domain.market.quote_row import QuoteRow, quote_row_copy
from vnpy_ashare.screener.data.market_benchmark import market_benchmark_change_pct
from vnpy_ashare.screener.data.screening_context import get_stock_industry_l1_map, get_stock_industry_map
from vnpy_ashare.screener.dimensions.momentum_bounds import momentum_change_bounds
from vnpy_ashare.screener.engine.snapshot_frame import (
    attach_industry_columns,
    change_pct_expr,
    frame_to_row_dicts,
    snapshot_rows_to_dataframe,
)
from vnpy_ashare.screener.preset.rules import _quote_row


def score_momentum_rows_polars(
    rows: list[Any],
    *,
    market_benchmark: float | None = None,
) -> list[dict[str, Any]]:
    """向量化动量评分，返回带 relative_strength 等字段的 dict 行。"""
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

    min_change, max_change = momentum_change_bounds()
    change = change_pct_expr()
    df = df.with_columns(change.alias("change_pct"))
    df = df.filter((change >= min_change) & (change <= max_change))
    if df.is_empty():
        return []

    benchmark = market_benchmark if market_benchmark is not None else market_benchmark_change_pct(frame_to_row_dicts(df))
    ind_avg = (
        df.filter(pl.col("industry").str.len_chars() > 0)
        .group_by("industry")
        .agg(change_pct_expr().mean().alias("_ind_avg"))
    )
    df = df.join(ind_avg, on="industry", how="left")
    has_industry_avg = pl.col("_ind_avg").is_not_null() & (pl.col("industry").str.len_chars() > 0)
    df = df.with_columns(
        pl.lit(benchmark).alias("benchmark_change_pct"),
        pl.when(has_industry_avg)
        .then(change - pl.col("_ind_avg"))
        .otherwise(change - pl.lit(benchmark))
        .round(2)
        .alias("relative_strength"),
        pl.when(has_industry_avg)
        .then(pl.concat_str([pl.lit("行业"), pl.col("industry")]))
        .otherwise(pl.lit("大盘"))
        .alias("strength_basis"),
        (change - pl.lit(benchmark)).round(2).alias("market_relative_strength"),
    )
    df = df.with_columns(
        pl.when(has_industry_avg)
        .then((change - pl.col("_ind_avg")).round(2))
        .otherwise(None)
        .alias("industry_relative_strength"),
    )
    df = df.sort("relative_strength", descending=True, nulls_last=True)
    return frame_to_row_dicts(df)


def build_momentum_hit_rows(
    filtered_rows: list[dict[str, Any]],
    *,
    pool_size: int,
    market_benchmark: float,
) -> list[QuoteRow]:
    """从已硬过滤、按 relative_strength 排序后的行构造 hit 行。"""
    hit_rows: list[QuoteRow] = []
    for item in filtered_rows[:pool_size]:
        hit_rows.append(
            quote_row_copy(
                _quote_row(item),
                benchmark_change_pct=market_benchmark,
                relative_strength=float(item.get("relative_strength") or 0),
                strength_basis=str(item.get("strength_basis") or "大盘"),
                market_relative_strength=float(item.get("market_relative_strength") or 0),
                **({"industry_relative_strength": float(item["industry_relative_strength"])} if item.get("industry_relative_strength") is not None else {}),
                **({"industry": item["industry"]} if item.get("industry") else {}),
            )
        )
    return hit_rows
