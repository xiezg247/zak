"""Polars 低 PE 维度（行业相对）。"""

from __future__ import annotations

from typing import Any

import polars as pl

from vnpy_ashare.domain.market.quote_row import coerce_quote_row
from vnpy_ashare.screener.data.screening_context import get_stock_industry_l1_map, get_stock_industry_map
from vnpy_ashare.screener.dimensions.base import DimensionHit, dimension_hit_row, rank_score
from vnpy_ashare.screener.engine.snapshot_frame import attach_industry_columns, frame_to_row_dicts, snapshot_rows_to_dataframe


def run_low_pe_polars(
    raw_rows: list[Any],
    *,
    pool_size: int,
    weight: float,
) -> tuple[list[DimensionHit], int] | None:
    if not raw_rows:
        return None

    industry_map = get_stock_industry_map()
    industry_l1_map = get_stock_industry_l1_map()
    df = snapshot_rows_to_dataframe(raw_rows)
    if df.is_empty():
        return None

    df = attach_industry_columns(
        df,
        industry_map=industry_map,
        industry_l1_map=industry_l1_map,
        drop_unmapped=True,
    )
    pe = pl.col("pe_ttm").cast(pl.Float64, strict=False).fill_null(0.0)
    df = df.filter((pe > 0) & (pe < 15))
    if df.is_empty():
        return None

    industry_pe = (
        df.filter(pl.col("industry").cast(pl.Utf8, strict=False).fill_null("").str.len_chars() > 0)
        .group_by("industry")
        .agg(pe.median().alias("_industry_pe_median"))
    )
    df = df.join(industry_pe, on="industry", how="left")
    median = pl.col("_industry_pe_median").cast(pl.Float64, strict=False)
    has_median = median.is_not_null() & (median > 0)
    df = df.filter(~has_median | (pe <= median * 0.85)).with_columns(
        pl.when(has_median).then(median).otherwise(None).alias("industry_pe_median"),
        pl.when(has_median).then((pe / median).round(2)).otherwise(None).alias("pe_vs_industry"),
    )
    if df.is_empty():
        return None

    df = df.sort("pe_ttm", descending=False, nulls_last=True).head(pool_size)
    result_rows = [coerce_quote_row(item) for item in frame_to_row_dicts(df)]

    hits: list[DimensionHit] = []
    for index, hit_row in enumerate(result_rows, start=1):
        vt_symbol = str(hit_row.get("vt_symbol") or "")
        if not vt_symbol:
            continue
        pe_val = float(hit_row.get("pe_ttm") or 0)
        vs_industry = hit_row.get("pe_vs_industry")
        industry_note = f"，行业相对 {vs_industry}" if vs_industry is not None else ""
        hits.append(
            DimensionHit(
                vt_symbol=vt_symbol,
                dimension_id="low_pe",
                label="估值",
                weight=weight,
                score=rank_score(index, len(result_rows)),
                reason=f"估值：PE(TTM) {pe_val:.2f}{industry_note}，排名第 {index}",
                row=dimension_hit_row(hit_row),
            )
        )
    return hits, len(raw_rows)
