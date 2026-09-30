"""Polars 连板维度（limit_times 排序）。"""

from __future__ import annotations

from typing import Any

from vnpy_ashare.domain.market.quote_row import QuoteRow, coerce_quote_row
from vnpy_ashare.quotes.core.enrich import get_cached_limit_times_map
from vnpy_ashare.quotes.radar.radar_limit_ladder import resolve_limit_times
from vnpy_ashare.domain.screener.dimension_hit import DimensionHit
from vnpy_ashare.screener.engine.dimensions.hits import quote_hits
from vnpy_ashare.screener.engine.dimensions.limit_common import collect_limit_candidate_rows


def _limit_board_reason(row: dict[str, Any], rank: int) -> str:
    boards = int(float(row.get("limit_times") or 1))
    industry = str(row.get("industry") or "—")
    change = float(row.get("change_pct") or 0)
    board_text = f"{boards}板" if boards >= 2 else "首板"
    return f"连板：{industry} {board_text}，涨幅 {change:+.2f}%，排名第 {rank}"


def run_limit_board_polars(
    rows: list[Any],
    *,
    pool_size: int,
    weight: float,
    total: int,
) -> tuple[list[DimensionHit], int]:
    limit_map = get_cached_limit_times_map()
    filtered = collect_limit_candidate_rows(rows, min_boards=1.0)
    if not filtered:
        return [], total

    candidates: list[QuoteRow] = []
    for item in filtered:
        row = coerce_quote_row(item)
        boards = resolve_limit_times(row, limit_times_map=limit_map)
        if boards >= 1:
            row["limit_times"] = boards
            candidates.append(row)

    candidates.sort(
        key=lambda row: (
            resolve_limit_times(row, limit_times_map=limit_map),
            float(row.get("amount") or 0),
            float(row.get("change_pct") or 0),
        ),
        reverse=True,
    )
    top_rows = candidates[:pool_size]

    return quote_hits(
        top_rows,
        dimension_id="limit_board",
        label="连板",
        weight=weight,
        reason_builder=_limit_board_reason,
        metric_key="limit_times",
    ), total
