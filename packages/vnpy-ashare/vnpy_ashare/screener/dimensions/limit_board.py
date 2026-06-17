"""连板涨停维度：limit_times + 涨停池。"""

from __future__ import annotations

from typing import Any

from vnpy_ashare.quotes.core.enrich import get_cached_limit_times_map
from vnpy_ashare.quotes.radar.radar_limit_ladder import (
    build_limit_ladder_candidates,
    resolve_limit_times,
)
from vnpy_ashare.screener.data.data_source import load_screening_quote_snapshot
from vnpy_ashare.screener.data.quotes_loader import MarketQuotesLoadError
from vnpy_ashare.screener.dimensions.base import DimensionHit, quote_hits
from vnpy_ashare.screener.sector.sector_summary import attach_industry


def run_limit_board(pool_size: int, *, weight: float) -> tuple[list[DimensionHit], int]:
    try:
        snapshot = load_screening_quote_snapshot()
    except MarketQuotesLoadError:
        return [], 0

    enriched = attach_industry(snapshot.rows)
    if not enriched:
        return [], snapshot.total

    limit_map = get_cached_limit_times_map()
    candidates = build_limit_ladder_candidates(enriched, limit_times_map=limit_map)
    if not candidates:
        return [], snapshot.total

    candidates.sort(
        key=lambda row: (
            resolve_limit_times(row, limit_times_map=limit_map),
            float(row.get("amount") or 0),
            float(row.get("change_pct") or 0),
        ),
        reverse=True,
    )
    top_rows = candidates[:pool_size]
    for row in top_rows:
        boards = resolve_limit_times(row, limit_times_map=limit_map)
        if boards >= 1:
            row["limit_times"] = boards

    return quote_hits(
        top_rows,
        dimension_id="limit_board",
        label="连板",
        weight=weight,
        reason_builder=_limit_board_reason,
        metric_key="limit_times",
    ), snapshot.total


def _limit_board_reason(row: dict[str, Any], rank: int) -> str:
    boards = int(float(row.get("limit_times") or 1))
    industry = str(row.get("industry") or "—")
    change = float(row.get("change_pct") or 0)
    board_text = f"{boards}板" if boards >= 2 else "首板"
    return f"连板：{industry} {board_text}，涨幅 {change:+.2f}%，排名第 {rank}"
