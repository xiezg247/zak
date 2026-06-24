"""换手维度：相对换手率排行。"""

from __future__ import annotations

from typing import Any

from vnpy_ashare.domain.market.quote_row import QuoteRow
from vnpy_ashare.screener.data.data_source import load_screening_quote_snapshot
from vnpy_ashare.screener.data.quotes_loader import MarketQuotesLoadError
from vnpy_ashare.screener.data.screening_context import get_avg_turnover_map
from vnpy_ashare.screener.dimensions.base import DimensionHit, quote_hits
from vnpy_ashare.screener.dimensions.scoring import relative_ratio
from vnpy_ashare.screener.hard_filters import apply_recipe_filters
from vnpy_ashare.screener.preset.rules import _quote_row


def run_turnover(pool_size: int, *, weight: float) -> tuple[list[DimensionHit], int]:
    try:
        snapshot = load_screening_quote_snapshot()
    except MarketQuotesLoadError:
        return [], 0

    avg_map = get_avg_turnover_map()
    enriched: list[dict[str, Any]] = []
    for row in snapshot.rows:
        vt_symbol = str(row.get("vt_symbol") or "")
        turnover = float(row.get("turnover_rate") or 0)
        if not vt_symbol or turnover <= 0:
            continue
        merged = dict(row)
        avg_turnover = float(avg_map.get(vt_symbol) or 0)
        merged["avg_turnover_rate"] = avg_turnover
        merged["relative_turnover"] = relative_ratio(turnover, avg_turnover)
        enriched.append(merged)

    if not enriched:
        return [], snapshot.total

    filtered = apply_recipe_filters(enriched)
    filtered.sort(key=lambda item: float(item.get("relative_turnover") or 0), reverse=True)
    rows: list[QuoteRow] = []
    for item in filtered[:pool_size]:
        base = _quote_row(item)
        base["avg_turnover_rate"] = float(item.get("avg_turnover_rate") or 0)
        base["relative_turnover"] = float(item.get("relative_turnover") or 0)
        rows.append(base)

    return quote_hits(
        rows,
        dimension_id="turnover",
        label="换手",
        weight=weight,
        metric_key="relative_turnover",
        reason_builder=_turnover_reason,
    ), snapshot.total


def _turnover_reason(row: dict[str, Any], rank: int) -> str:
    turnover = float(row.get("turnover_rate") or 0)
    relative = float(row.get("relative_turnover") or 0)
    avg_turnover = float(row.get("avg_turnover_rate") or 0)
    if avg_turnover > 0:
        return f"换手：{turnover:.2f}%（均 {avg_turnover:.2f}%），相对 {relative:.2f}，排名第 {rank}"
    return f"换手：{turnover:.2f}%，排名第 {rank}"
