"""Polars 首板人气维度。"""

from __future__ import annotations

from typing import Any

from vnpy_ashare.domain.market.quote_row import QuoteRow, coerce_quote_row
from vnpy_ashare.quotes.core.enrich import get_cached_limit_times_map
from vnpy_ashare.quotes.radar.radar_first_board import rank_first_board_pool
from vnpy_ashare.quotes.radar.radar_limit_ladder import resolve_limit_times
from vnpy_ashare.screener.data.screening_context import get_stock_industry_l1_map, get_stock_industry_map
from vnpy_ashare.screener.dimensions.base import DimensionHit, dimension_hit_row
from vnpy_ashare.screener.dimensions.first_board import _first_board_reason
from vnpy_ashare.screener.engine.dimensions.limit_common import collect_limit_candidate_rows
from vnpy_ashare.screener.engine.sector_stats import compute_sector_distribution_polars
from vnpy_ashare.screener.engine.snapshot_frame import attach_industry_columns, snapshot_rows_to_dataframe
from vnpy_ashare.trading.signals.intraday_seal_time import attach_first_time_fields


def _strong_industries_polars(rows: list[Any]) -> set[str]:
    industry_map = get_stock_industry_map()
    industry_l1_map = get_stock_industry_l1_map()
    df = snapshot_rows_to_dataframe(rows)
    if df.is_empty():
        return set()
    df = attach_industry_columns(
        df,
        industry_map=industry_map,
        industry_l1_map=industry_l1_map,
        drop_unmapped=True,
    )
    distribution = compute_sector_distribution_polars(df, top_n=5, min_stocks=3)
    if distribution.is_empty():
        return set()
    return {str(value).strip() for value in distribution["industry"].to_list() if str(value).strip()}


def run_first_board_polars(
    rows: list[Any],
    *,
    pool_size: int,
    weight: float,
    total: int,
) -> tuple[list[DimensionHit], int]:
    limit_map = get_cached_limit_times_map()
    filtered = collect_limit_candidate_rows(rows, min_boards=1.0, max_boards=1.0)
    if not filtered:
        return [], total

    candidates: list[QuoteRow] = []
    for item in filtered:
        row = coerce_quote_row(item)
        if resolve_limit_times(row, limit_times_map=limit_map) == 1:
            candidates.append(row)
    if not candidates:
        return [], total

    attach_first_time_fields(candidates)
    strong = _strong_industries_polars(rows)
    ranked = rank_first_board_pool(candidates, top_n=pool_size, strong_industries=strong)

    hits: list[DimensionHit] = []
    for source_row, popularity, seal_label in ranked:
        vt_symbol = str(source_row.get("vt_symbol") or "")
        if not vt_symbol:
            continue
        payload = dict(source_row)
        payload["first_board_score"] = popularity
        if seal_label:
            payload["seal_time_label"] = seal_label
        hits.append(
            DimensionHit(
                vt_symbol=vt_symbol,
                dimension_id="first_board",
                label="首板",
                weight=weight,
                score=popularity,
                reason=_first_board_reason(payload, seal_label),
                row=dimension_hit_row(source_row),
            )
        )
    return hits, total
