"""概念板块维度：同花顺概念指数强势成分。"""

from __future__ import annotations

from typing import Any

from vnpy_ashare.screener.data.data_source import load_screening_quote_snapshot
from vnpy_ashare.screener.data.quotes_loader import MarketQuotesLoadError
from vnpy_ashare.screener.dimensions.base import DimensionHit


def run_concept_strength(pool_size: int, *, weight: float) -> tuple[list[DimensionHit], int]:
    from vnpy_ashare.screener.engine.dimensions.concept_strength import run_concept_strength_polars

    try:
        snapshot = load_screening_quote_snapshot()
    except MarketQuotesLoadError:
        return [], 0

    result = run_concept_strength_polars(
        list(snapshot.rows),
        pool_size=pool_size,
        weight=weight,
        total=snapshot.total,
    )
    if result is None:
        return [], snapshot.total
    return result


def _concept_reason(row: dict[str, Any], rank: int) -> str:
    concept = str(row.get("concept_name") or "未知")
    change = float(row.get("change_pct") or 0)
    return f"概念：{concept} 强势，涨幅 {change:+.2f}%，排名第 {rank}"
