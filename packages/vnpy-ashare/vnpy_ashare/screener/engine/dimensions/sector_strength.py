"""Polars 板块强度维度。"""

from __future__ import annotations

from typing import Any

import polars as pl

from vnpy_ashare.domain.market.quote_row import QuoteRow
from vnpy_ashare.screener.data.screening_context import get_stock_industry_l1_map, get_stock_industry_map
from vnpy_ashare.screener.dimensions.base import DimensionHit, quote_hits
from vnpy_ashare.screener.dimensions.sector_strength import _sector_reason
from vnpy_ashare.screener.engine.sector_stats import compute_sector_distribution_polars
from vnpy_ashare.screener.engine.snapshot_frame import attach_industry_columns, change_pct_expr, frame_to_row_dicts, snapshot_rows_to_dataframe
from vnpy_ashare.screener.preset.rules import _quote_row


def run_sector_strength_polars(
    rows: list[Any],
    *,
    pool_size: int,
    weight: float,
    total: int,
) -> tuple[list[DimensionHit], int]:
    industry_map = get_stock_industry_map()
    industry_l1_map = get_stock_industry_l1_map()
    df = snapshot_rows_to_dataframe(rows)
    if df.is_empty():
        return [], total

    df = attach_industry_columns(
        df,
        industry_map=industry_map,
        industry_l1_map=industry_l1_map,
        drop_unmapped=True,
    )
    if df.is_empty():
        return [], total

    distribution = compute_sector_distribution_polars(df, top_n=10, min_stocks=3)
    if distribution.is_empty():
        return [], total

    strong = distribution.head(5)["industry"].to_list()
    if not strong:
        return [], total

    stats = distribution.select(
        pl.col("industry"),
        pl.col("advance_pct").alias("industry_advance_pct"),
    )
    candidates = (
        df.filter(pl.col("industry").is_in(strong))
        .join(stats, on="industry", how="left")
        .with_columns(change_pct_expr().alias("change_pct"))
        .sort("change_pct", descending=True, nulls_last=True)
        .head(pool_size)
    )
    if candidates.is_empty():
        return [], total

    hit_rows: list[QuoteRow] = []
    for item in frame_to_row_dicts(candidates):
        base = _quote_row(item)
        base["industry"] = str(item.get("industry") or "")
        if item.get("industry_advance_pct") is not None:
            base["industry_advance_pct"] = float(item.get("industry_advance_pct") or 0)
        hit_rows.append(base)

    return quote_hits(
        hit_rows,
        dimension_id="sector_strength",
        label="板块",
        weight=weight,
        reason_builder=lambda row, rank: _sector_reason(row, rank),
    ), total
