"""雷达行相对强度（行业 / 大盘）副标题。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from vnpy_ashare.quotes.radar.radar_models import RadarRow

from vnpy_ashare.domain.market.quote_row import QuoteRowLike, QuoteRowsLike
from vnpy_ashare.quotes.format import format_pct
from vnpy_ashare.screener.data.market_benchmark import (
    industry_avg_change_map,
    market_benchmark_change_pct,
    relative_strength_pct,
    resolve_relative_strength,
)
from vnpy_ashare.screener.data.quotes_loader import MarketQuotesLoadError
from vnpy_ashare.screener.data.screening_context import get_stock_industry_map
from vnpy_ashare.screener.sector.sector_summary import attach_industry

_MIN_INDUSTRY_POOL = 20


def _market_rows_for_relative_strength(snapshot_rows: QuoteRowsLike | None) -> QuoteRowsLike:
    """行业均值须基于足够大的样本池；单票或过小 pool 会退化为 +0.00%。"""
    if snapshot_rows is not None and len(snapshot_rows) >= _MIN_INDUSTRY_POOL:
        return snapshot_rows
    try:
        from vnpy_ashare.screener.data.data_source import load_screening_quote_snapshot

        return load_screening_quote_snapshot().rows
    except MarketQuotesLoadError:
        return snapshot_rows or []


def build_relative_strength_subline(
    row: QuoteRowLike,
    *,
    snapshot_rows: QuoteRowsLike | None = None,
) -> tuple[str, str] | None:
    """返回 (sub_label, sub_value)，无有效涨幅时返回 None。"""
    change = row.get("change_pct") if row.get("change_pct") not in (None, "") else row.get("pct_chg")
    if change is None or change == "":
        return None
    try:
        float(change)
    except (TypeError, ValueError):
        return None

    pool = _market_rows_for_relative_strength(snapshot_rows)
    if not pool:
        pool = [row]
    industry_map = get_stock_industry_map()
    enriched = attach_industry(pool, industry_map=industry_map)
    market_benchmark = market_benchmark_change_pct(enriched or pool)
    industry_avg = industry_avg_change_map(enriched)

    merged: QuoteRowLike = row
    if industry_map and not merged.get("industry"):
        enriched_one = attach_industry([merged], industry_map=industry_map)
        if enriched_one:
            merged = enriched_one[0]

    _, basis = resolve_relative_strength(
        merged,
        market_benchmark=market_benchmark,
        industry_avg_map=industry_avg,
    )
    market_rs = relative_strength_pct(merged, market_benchmark)
    industry = str(merged.get("industry") or "").strip()
    if basis.startswith("行业") and industry and industry in industry_avg:
        industry_rs = relative_strength_pct(merged, float(industry_avg[industry]))
        return "相对强度", f"行业{format_pct(industry_rs)} 大盘{format_pct(market_rs)}"
    return "相对大盘", format_pct(market_rs)


def enrich_radar_row_relative_strength(
    row: RadarRow,
    quote_row: dict[str, Any],
    *,
    snapshot_rows: QuoteRowsLike | None = None,
) -> RadarRow:
    """为雷达行补全相对强度副标题。"""
    sub = build_relative_strength_subline(quote_row, snapshot_rows=snapshot_rows)
    if sub is None:
        return row

    return row.model_copy(update={"sub_label": sub[0], "sub_value": sub[1]})
