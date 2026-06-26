"""Polars 20cm 弹性维度。"""

from __future__ import annotations

from typing import Any

import polars as pl

from vnpy_ashare.domain.market.quote_row import QuoteRow, quote_row_copy
from vnpy_ashare.screener.data.screening_context import get_stock_industry_l1_map, get_stock_industry_map
from vnpy_ashare.screener.dimensions.base import DimensionHit, dimension_hit_row
from vnpy_ashare.screener.dimensions.cm20_elastic import (
    _CM20_MAX_MV_YI,
    _CM20_MIN_CHANGE,
    _CM20_SWEET_MV_YI,
    _cm20_reason,
    cm20_elastic_score,
)
from vnpy_ashare.screener.engine.snapshot_frame import (
    attach_industry_columns,
    change_pct_expr,
    frame_to_row_dicts,
    snapshot_rows_to_dataframe,
)
from vnpy_ashare.screener.hard_filters import apply_recipe_filters


def _is_cm20_expr(symbol_col: pl.Expr) -> pl.Expr:
    return symbol_col.str.starts_with("300") | symbol_col.str.starts_with("688")


def _size_score_expr(mv_yi: pl.Expr) -> pl.Expr:
    return (
        pl.when(mv_yi <= 0)
        .then(0.5)
        .when(mv_yi < _CM20_SWEET_MV_YI[0])
        .then(0.35)
        .when(mv_yi <= _CM20_SWEET_MV_YI[1])
        .then(1.0)
        .when(mv_yi <= _CM20_MAX_MV_YI)
        .then(0.65)
        .otherwise(0.25)
    )


def run_cm20_elastic_polars(
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

    symbol = pl.coalesce(
        pl.col("symbol").cast(pl.Utf8, strict=False),
        pl.col("vt_symbol").cast(pl.Utf8, strict=False).str.split(".").list.first(),
    ).fill_null("")
    change = change_pct_expr()
    mv_wan = pl.coalesce(
        pl.col("total_mv").cast(pl.Float64, strict=False),
        pl.col("circ_mv").cast(pl.Float64, strict=False),
    ).fill_null(0.0)
    mv_yi = mv_wan / 10_000.0
    amount = pl.col("amount").cast(pl.Float64, strict=False).fill_null(0.0)

    df = df.filter(_is_cm20_expr(symbol) & (change >= _CM20_MIN_CHANGE))
    if df.is_empty():
        return [], total

    filtered = apply_recipe_filters(frame_to_row_dicts(df))
    if not filtered:
        return [], total

    df = pl.DataFrame(filtered, infer_schema_length=max(len(filtered), 1))
    symbol = pl.coalesce(
        pl.col("symbol").cast(pl.Utf8, strict=False),
        pl.col("vt_symbol").cast(pl.Utf8, strict=False).str.split(".").list.first(),
    ).fill_null("")
    change = change_pct_expr()
    mv_wan = pl.coalesce(
        pl.col("total_mv").cast(pl.Float64, strict=False),
        pl.col("circ_mv").cast(pl.Float64, strict=False),
    ).fill_null(0.0)
    mv_yi = mv_wan / 10_000.0
    amount = pl.col("amount").cast(pl.Float64, strict=False).fill_null(0.0)
    amount_rank = (amount.rank(method="average") / pl.len()).fill_null(0.0)
    change_score = (change / 20.0).clip(0.0, 1.0)
    size_score = _size_score_expr(mv_yi)
    elastic = ((change_score * 0.55 + size_score * 0.30 + amount_rank.clip(0.0, 1.0) * 0.15) * 100.0).round(1)

    df = (
        df.with_columns(
            symbol.alias("_symbol"),
            elastic.alias("_elastic_score"),
            change.alias("_change"),
            pl.lit("20cm").alias("board_tag"),
        )
        .sort(["_elastic_score", "_change"], descending=[True, True], nulls_last=True)
        .head(pool_size)
    )

    hits: list[DimensionHit] = []
    for item in frame_to_row_dicts(df):
        vt_symbol = str(item.get("vt_symbol") or "")
        if not vt_symbol:
            continue
        row = quote_row_copy(item, board_tag="20cm")
        score = float(item.get("_elastic_score") or cm20_elastic_score(row, amount_rank=0.5))
        hits.append(
            DimensionHit(
                vt_symbol=vt_symbol,
                dimension_id="cm20_elastic",
                label="20cm",
                weight=weight,
                score=score,
                reason=_cm20_reason(row, score),
                row=dimension_hit_row(row),
            )
        )
    return hits, total
