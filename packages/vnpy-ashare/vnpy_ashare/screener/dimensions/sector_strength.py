"""板块维度：强势行业成分股加分。"""

from __future__ import annotations

from typing import Any

from vnpy_ashare.screener.data.data_source import load_screening_quote_snapshot
from vnpy_ashare.screener.data.quotes_loader import MarketQuotesLoadError
from vnpy_ashare.screener.dimensions.base import DimensionHit, quote_hits
from vnpy_ashare.screener.preset.rules import _quote_row
from vnpy_ashare.screener.sector.sector_summary import attach_industry, compute_sector_distribution, top_industries_by_momentum


def run_sector_strength(pool_size: int, *, weight: float) -> tuple[list[DimensionHit], int]:
    try:
        snapshot = load_screening_quote_snapshot()
    except MarketQuotesLoadError:
        return [], 0

    enriched = attach_industry(snapshot.rows)
    if not enriched:
        return [], snapshot.total

    distribution = compute_sector_distribution(
        enriched,
        top_n=10,
        min_stocks=3,
    )
    strong_industries = {str(item["industry"]) for item in distribution[:5]}
    if not strong_industries:
        strong_industries = set(top_industries_by_momentum(enriched, top_industry_count=5, min_stocks_per_industry=3))
    if not strong_industries:
        return [], snapshot.total

    candidates: list[dict[str, Any]] = []
    for row in enriched:
        industry = str(row.get("industry") or "")
        if industry not in strong_industries:
            continue
        base = _quote_row(row)
        base["industry"] = industry
        dist = next((item for item in distribution if str(item.get("industry")) == industry), None)
        if dist:
            base["industry_advance_pct"] = float(dist.get("advance_pct") or 0)
        candidates.append(base)

    candidates.sort(key=lambda item: float(item.get("change_pct") or 0), reverse=True)
    top_rows = candidates[:pool_size]

    return quote_hits(
        top_rows,
        dimension_id="sector_strength",
        label="板块",
        weight=weight,
        reason_builder=lambda row, rank: _sector_reason(row, rank),
    ), snapshot.total


def _sector_reason(row: dict, rank: int) -> str:
    industry = str(row.get("industry") or "未知")
    change = float(row.get("change_pct") or 0)
    advance = row.get("industry_advance_pct")
    advance_note = f"，上涨占比 {float(advance):.0f}%" if advance is not None else ""
    return f"板块：{industry} 强势{advance_note}，涨幅 {change:+.2f}%，排名第 {rank}"
