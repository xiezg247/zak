"""雷达行相对强度（行业 / 大盘）副标题。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from vnpy_ashare.quotes.radar.radar_models import RadarRow

from vnpy_ashare.quotes.radar.radar_models import format_pct
from vnpy_ashare.screener.data.market_benchmark import (
    industry_avg_change_map,
    market_benchmark_change_pct,
    relative_strength_pct,
    resolve_relative_strength,
)
from vnpy_ashare.screener.data.screening_context import get_stock_industry_map
from vnpy_ashare.screener.sector.sector_summary import attach_industry


def build_relative_strength_subline(
    row: dict[str, Any],
    *,
    snapshot_rows: list[dict[str, Any]] | None = None,
) -> tuple[str, str] | None:
    """返回 (sub_label, sub_value)，无有效涨幅时返回 None。"""
    change = row.get("change_pct") if row.get("change_pct") not in (None, "") else row.get("pct_chg")
    if change is None or change == "":
        return None
    try:
        float(change)
    except (TypeError, ValueError):
        return None

    pool = snapshot_rows or [row]
    industry_map = get_stock_industry_map()
    enriched = attach_industry(pool, industry_map=industry_map)
    market_benchmark = market_benchmark_change_pct(enriched or pool)
    industry_avg = industry_avg_change_map(enriched)

    merged = dict(row)
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


def enrich_radar_row_relative_strength(row: RadarRow, quote_row: dict[str, Any]) -> RadarRow:
    """为雷达行补全相对强度副标题（若尚无有效副标题）。"""
    if row.sub_label in ("相对强度", "相对大盘") and row.sub_value and row.sub_value != "—":
        return row
    sub = build_relative_strength_subline(quote_row)
    if sub is None:
        return row
    from dataclasses import replace

    return replace(row, sub_label=sub[0], sub_value=sub[1])
