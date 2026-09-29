"""20cm 弹性维度入口。

打分与 reason 在 engine.dimensions.cm20_elastic。
"""

from __future__ import annotations

from vnpy_ashare.screener.dimensions.base import DimensionHit, load_quote_snapshot_for_dimension
from vnpy_ashare.screener.engine.dimensions.cm20_elastic import cm20_elastic_score, is_cm20_row

__all__ = ["cm20_elastic_score", "is_cm20_row", "run_cm20_elastic"]


def run_cm20_elastic(pool_size: int, *, weight: float) -> tuple[list[DimensionHit], int]:
    from vnpy_ashare.screener.engine.dimensions.cm20_elastic import run_cm20_elastic_polars

    loaded = load_quote_snapshot_for_dimension()
    if loaded is None:
        return [], 0
    rows, total = loaded
    result = run_cm20_elastic_polars(rows, pool_size=pool_size, weight=weight, total=total)
    if result is not None:
        return result
    return [], total
