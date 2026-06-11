"""行业/板块汇总（选股解读与 sector_strength 维度共用）。"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from vnpy_ashare.domain.symbols import vt_symbol_to_ts_code
from vnpy_ashare.integrations.tushare.factors import fetch_stock_industry_map


def attach_industry(rows: list[dict[str, Any]], industry_map: dict[str, str] | None = None) -> list[dict[str, Any]]:
    """为行情行附加 ``industry`` 字段。"""
    mapping = industry_map if industry_map is not None else fetch_stock_industry_map()
    enriched: list[dict[str, Any]] = []
    for row in rows:
        ts_code = vt_symbol_to_ts_code(str(row.get("vt_symbol") or ""))
        industry = mapping.get(ts_code or "", "").strip() if ts_code else ""
        if not industry:
            continue
        merged = dict(row)
        merged["industry"] = industry
        enriched.append(merged)
    return enriched


def compute_sector_distribution(
    rows: list[dict[str, Any]],
    *,
    top_n: int = 8,
    min_stocks: int = 2,
) -> list[dict[str, Any]]:
    """按行业统计标的数与平均涨幅，降序返回 Top N。"""
    buckets: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        industry = str(row.get("industry") or "").strip()
        if not industry:
            continue
        pct = float(row.get("change_pct") or row.get("pct_chg") or 0)
        buckets[industry].append(pct)

    stats: list[dict[str, Any]] = []
    for industry, pcts in buckets.items():
        if len(pcts) < min_stocks:
            continue
        avg_pct = sum(pcts) / len(pcts)
        stats.append(
            {
                "industry": industry,
                "count": len(pcts),
                "avg_change_pct": round(avg_pct, 2),
            }
        )
    stats.sort(key=lambda item: (float(item["avg_change_pct"]), int(item["count"])), reverse=True)
    return stats[: max(1, top_n)]


def top_industries_by_momentum(
    rows: list[dict[str, Any]],
    *,
    top_industry_count: int = 5,
    min_stocks_per_industry: int = 3,
) -> list[str]:
    """返回当日平均涨幅靠前的行业名列表。"""
    distribution = compute_sector_distribution(
        rows,
        top_n=top_industry_count * 2,
        min_stocks=min_stocks_per_industry,
    )
    return [str(item["industry"]) for item in distribution[:top_industry_count]]
