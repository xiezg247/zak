"""Polars 概念板块维度。"""

from __future__ import annotations

from typing import Any

import polars as pl

from vnpy_ashare.domain.market.quote_row import QuoteRow
from vnpy_ashare.integrations.tushare.concept_board import build_hot_concept_vt_symbol_map
from vnpy_ashare.screener.dimensions.base import DimensionHit, quote_hits
from vnpy_ashare.screener.dimensions.concept_strength import _concept_reason
from vnpy_ashare.screener.engine.snapshot_frame import change_pct_expr, frame_to_row_dicts, snapshot_rows_to_dataframe
from vnpy_ashare.screener.preset.rules import _quote_row


def run_concept_strength_polars(
    rows: list[Any],
    *,
    pool_size: int,
    weight: float,
    total: int,
) -> tuple[list[DimensionHit], int] | None:
    vt_to_concept, hot_names = build_hot_concept_vt_symbol_map()
    if not vt_to_concept:
        return None

    df = snapshot_rows_to_dataframe(rows)
    if df.is_empty():
        return None

    map_df = pl.DataFrame(
        {"vt_symbol": list(vt_to_concept.keys()), "concept_name": list(vt_to_concept.values())},
    )
    df = (
        df.filter(pl.col("vt_symbol").cast(pl.Utf8, strict=False).fill_null("").str.len_chars() > 0)
        .join(map_df, on="vt_symbol", how="inner")
        .with_columns(
            change_pct_expr().alias("change_pct"),
            pl.lit(hot_names[:5]).alias("hot_concepts"),
        )
        .sort("change_pct", descending=True, nulls_last=True)
        .head(pool_size)
    )
    if df.is_empty():
        return None

    hit_rows: list[QuoteRow] = []
    for item in frame_to_row_dicts(df):
        base = _quote_row(item)
        base["concept_name"] = str(item.get("concept_name") or "")
        base["hot_concepts"] = item.get("hot_concepts") or hot_names[:5]
        hit_rows.append(base)

    return quote_hits(
        hit_rows,
        dimension_id="concept_strength",
        label="概念",
        weight=weight,
        reason_builder=lambda row, rank: _concept_reason(row, rank),
    ), total
