"""估值维度：行业相对低 PE 排行。"""

from __future__ import annotations

from collections import defaultdict

from vnpy_ashare.screener.data.data_source import fetch_fundamental_screening_rows
from vnpy_ashare.screener.data.screening_context import get_stock_industry_map
from vnpy_ashare.screener.dimensions.base import DimensionHit, rank_score
from vnpy_ashare.screener.preset.rules import apply_low_pe
from vnpy_ashare.screener.sector.sector_summary import attach_industry


def _industry_pe_median(rows: list[dict]) -> dict[str, float]:
    buckets: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        pe = float(row.get("pe_ttm") or 0)
        industry = str(row.get("industry") or "").strip()
        if industry and pe > 0:
            buckets[industry].append(pe)
    return {
        industry: sorted(values)[len(values) // 2]
        for industry, values in buckets.items()
        if values
    }


def run_low_pe(pool_size: int, *, weight: float) -> tuple[list[DimensionHit], int]:
    raw_rows, _trade_date, _ = fetch_fundamental_screening_rows()
    if not raw_rows:
        return [], 0

    industry_map = get_stock_industry_map()
    enriched = attach_industry(raw_rows, industry_map=industry_map)
    industry_median = _industry_pe_median(enriched)

    filtered: list[dict] = []
    for row in enriched:
        item = dict(row)
        pe = float(item.get("pe_ttm") or 0)
        if pe <= 0 or pe >= 15:
            continue
        industry = str(item.get("industry") or "").strip()
        if industry and industry in industry_median:
            median_pe = industry_median[industry]
            if median_pe > 0 and pe > median_pe * 0.85:
                continue
            item["industry_pe_median"] = median_pe
            item["pe_vs_industry"] = round(pe / median_pe, 2)
        filtered.append(item)

    if not filtered:
        rows = apply_low_pe(raw_rows, top_n=pool_size)
    else:
        filtered.sort(key=lambda item: float(item.get("pe_ttm") or 0))
        rows = filtered[:pool_size]

    hits: list[DimensionHit] = []
    for index, row in enumerate(rows, start=1):
        vt_symbol = str(row.get("vt_symbol") or "")
        if not vt_symbol:
            continue
        pe = float(row.get("pe_ttm") or 0)
        vs_industry = row.get("pe_vs_industry")
        industry_note = f"，行业相对 {vs_industry}" if vs_industry is not None else ""
        hits.append(
            DimensionHit(
                vt_symbol=vt_symbol,
                dimension_id="low_pe",
                label="估值",
                weight=weight,
                score=rank_score(index, len(rows)),
                reason=f"估值：PE(TTM) {pe:.2f}{industry_note}，排名第 {index}",
                row=dict(row),
            )
        )
    return hits, len(raw_rows)
