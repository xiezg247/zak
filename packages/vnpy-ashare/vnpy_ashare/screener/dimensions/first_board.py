"""首板人气维度：limit_times=1 + 封板时间代理。"""

from __future__ import annotations

from typing import Any

from vnpy_ashare.quotes.core.enrich import get_cached_limit_times_map
from vnpy_ashare.quotes.radar.radar_first_board import (
    build_first_board_candidates,
    format_seal_time_label,
    load_limit_list_first_time_map,
    rank_first_board_pool,
)
from vnpy_ashare.screener.data.data_source import load_screening_quote_snapshot
from vnpy_ashare.screener.data.quotes_loader import MarketQuotesLoadError
from vnpy_ashare.screener.dimensions.base import DimensionHit
from vnpy_ashare.screener.sector.sector_summary import attach_industry


def run_first_board(pool_size: int, *, weight: float) -> tuple[list[DimensionHit], int]:
    try:
        snapshot = load_screening_quote_snapshot()
    except MarketQuotesLoadError:
        return [], 0

    enriched = attach_industry(snapshot.rows)
    if not enriched:
        return [], snapshot.total

    limit_map = get_cached_limit_times_map()
    candidates = build_first_board_candidates(enriched, limit_times_map=limit_map)
    if not candidates:
        return [], snapshot.total

    first_time_map = load_limit_list_first_time_map()
    ranked = rank_first_board_pool(
        candidates,
        first_time_map=first_time_map,
        top_n=pool_size,
    )

    hits: list[DimensionHit] = []
    for row, popularity, seal_label in ranked:
        vt_symbol = str(row.get("vt_symbol") or "")
        if not vt_symbol:
            continue
        row = dict(row)
        row["first_board_score"] = popularity
        if seal_label:
            row["seal_time_label"] = seal_label
        hits.append(
            DimensionHit(
                vt_symbol=vt_symbol,
                dimension_id="first_board",
                label="首板",
                weight=weight,
                score=popularity,
                reason=_first_board_reason(row, seal_label),
                row=row,
            )
        )
    return hits, snapshot.total


def _first_board_reason(row: dict[str, Any], seal_label: str) -> str:
    industry = str(row.get("industry") or "—")
    change = float(row.get("change_pct") or 0)
    seal = seal_label or format_seal_time_label(str(row.get("first_time") or "")) or "封板时间待补"
    score = float(row.get("first_board_score") or 0)
    return f"首板：{industry} {seal}，人气 {score:.0f}，涨幅 {change:+.2f}%"
