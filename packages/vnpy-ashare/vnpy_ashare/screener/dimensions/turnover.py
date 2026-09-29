"""换手维度：相对换手率排行。

dimensions 侧仅负责取数入口；打分在 engine.dimensions.turnover。
"""

from __future__ import annotations

from vnpy_ashare.screener.dimensions.base import DimensionHit, load_quote_snapshot_for_dimension


def run_turnover(pool_size: int, *, weight: float) -> tuple[list[DimensionHit], int]:
    from vnpy_ashare.screener.engine.dimensions.turnover import run_turnover_polars

    loaded = load_quote_snapshot_for_dimension()
    if loaded is None:
        return [], 0
    rows, total = loaded
    return run_turnover_polars(rows, pool_size=pool_size, weight=weight, total=total)
