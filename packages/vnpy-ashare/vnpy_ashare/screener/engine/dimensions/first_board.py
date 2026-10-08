"""Polars 首板人气维度。"""

from __future__ import annotations

from typing import Any

from vnpy_ashare.screener.engine.dimensions.hits import run_with_quote_snapshot
from vnpy_ashare.domain.market.quote_row import QuoteRow, coerce_quote_row
from vnpy_ashare.quotes.core.enrich import get_cached_limit_times_map
from vnpy_ashare.quotes.radar.radar_first_board import rank_first_board_pool
from vnpy_ashare.quotes.radar.radar_limit_ladder import resolve_limit_times
from vnpy_ashare.screener.data.screening_factor_maps import get_stock_industry_l1_map, get_stock_industry_map
from vnpy_ashare.domain.screener.dimension_hit import DimensionHit, dimension_hit_row
from vnpy_ashare.screener.engine.dimensions.limit_common import collect_limit_candidate_rows
from vnpy_ashare.screener.engine.sector_stats import compute_sector_distribution_polars
from vnpy_ashare.screener.engine.snapshot_frame import attach_industry_columns, snapshot_rows_to_dataframe
from vnpy_ashare.trading.signals.intraday_seal_time import attach_first_time_fields
from vnpy_ashare.trading.signals.seal_time import format_seal_time_label


def _first_board_reason(row: dict[str, Any], seal_label: str) -> str:
    industry = str(row.get("industry") or "—")
    change = float(row.get("change_pct") or 0)
    seal = seal_label or format_seal_time_label(str(row.get("first_time") or "")) or "封板时间待补"
    score = float(row.get("first_board_score") or 0)
    strength_raw = row.get("seal_strength_score")
    strength_hint = ""
    if strength_raw not in (None, ""):
        try:
            strength_hint = f"，封单强度 {float(str(strength_raw)) * 100:.0f}"
        except (TypeError, ValueError):
            strength_hint = ""
    reopen_label = str(row.get("seal_reopen_label") or "").strip()
    reopen_hint = f"，{reopen_label}" if reopen_label else ""
    return f"首板：{industry} {seal}{strength_hint}{reopen_hint}，人气 {score:.0f}，涨幅 {change:+.2f}%"


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

def run_first_board(pool_size: int, *, weight: float) -> tuple[list[DimensionHit], int]:
    return run_with_quote_snapshot(pool_size, weight=weight, runner=run_first_board_polars)
