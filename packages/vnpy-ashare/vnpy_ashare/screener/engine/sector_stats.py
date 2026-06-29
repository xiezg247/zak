"""Polars 行业分布统计。"""

from __future__ import annotations

import polars as pl

from vnpy_ashare.screener.engine.snapshot_frame import change_pct_expr


def compute_sector_distribution_polars(
    df: pl.DataFrame,
    *,
    top_n: int = 8,
    min_stocks: int = 2,
    sector_col: str = "industry",
) -> pl.DataFrame:
    if df.is_empty() or sector_col not in df.columns:
        return pl.DataFrame()

    change = change_pct_expr()
    scoped = df.filter(pl.col(sector_col).cast(pl.Utf8, strict=False).fill_null("").str.len_chars() > 0)
    if scoped.is_empty():
        return pl.DataFrame()

    stats = (
        scoped.group_by(sector_col)
        .agg(
            pl.len().alias("count"),
            change.mean().round(2).alias("avg_change_pct"),
            (change > 0).mean().alias("advance_ratio"),
        )
        .filter(pl.col("count") >= min_stocks)
        .with_columns((pl.col("advance_ratio") * 100).round(1).alias("advance_pct"))
        .with_columns(pl.col(sector_col).alias("industry"))
        .sort(["avg_change_pct", "advance_ratio", "count"], descending=[True, True, True])
        .head(max(1, top_n))
    )
    return stats
