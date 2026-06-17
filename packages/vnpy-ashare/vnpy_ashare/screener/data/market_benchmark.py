"""选股用大盘 / 行业基准涨幅（相对强度）。"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from vnpy_ashare.integrations.tickflow.quotes import fetch_index_ticker

_HS300_LABEL = "沪深300"
_HS300_SYMBOL = "000300.SH"


def market_benchmark_change_pct(rows: list[dict[str, Any]]) -> float:
    """优先沪深300涨幅；不可用则退回全市场涨幅均值。"""
    try:
        for label, quote in fetch_index_ticker():
            if label == _HS300_LABEL or str(quote.symbol or "") == _HS300_SYMBOL:
                return float(quote.change_pct or 0)
    except Exception:
        pass

    changes = [float(row.get("change_pct") or 0) for row in rows]
    if not changes:
        return 0.0
    return sum(changes) / len(changes)


def industry_avg_change_map(rows: list[dict[str, Any]]) -> dict[str, float]:
    """行业平均涨幅（需行内已有 industry）。"""
    buckets: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        industry = str(row.get("industry") or "").strip()
        if not industry:
            continue
        buckets[industry].append(float(row.get("change_pct") or row.get("pct_chg") or 0))
    return {industry: sum(values) / len(values) for industry, values in buckets.items() if values}


def relative_strength_pct(row: dict[str, Any], benchmark_change_pct: float) -> float:
    change = float(row.get("change_pct") or row.get("pct_chg") or 0)
    return round(change - benchmark_change_pct, 2)


def resolve_relative_strength(
    row: dict[str, Any],
    *,
    market_benchmark: float,
    industry_avg_map: dict[str, float],
) -> tuple[float, str]:
    """相对行业优先；无行业时相对大盘。"""
    industry = str(row.get("industry") or "").strip()
    if industry and industry in industry_avg_map:
        avg = float(industry_avg_map[industry])
        rs = relative_strength_pct(row, avg)
        return rs, f"行业{industry}"
    rs = relative_strength_pct(row, market_benchmark)
    return rs, "大盘"
