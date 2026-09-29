"""概念板块维度：同花顺概念指数强势成分。

dimensions 侧仅负责取数入口；打分与 reason 在 engine.dimensions.concept_strength。
"""

from __future__ import annotations

from vnpy_ashare.screener.dimensions.base import DimensionHit, load_quote_snapshot_for_dimension


def run_concept_strength(pool_size: int, *, weight: float) -> tuple[list[DimensionHit], int]:
    from vnpy_ashare.screener.engine.dimensions.concept_strength import run_concept_strength_polars

    loaded = load_quote_snapshot_for_dimension()
    if loaded is None:
        return [], 0
    rows, total = loaded
    result = run_concept_strength_polars(rows, pool_size=pool_size, weight=weight, total=total)
    if result is None:
        return [], total
    return result
