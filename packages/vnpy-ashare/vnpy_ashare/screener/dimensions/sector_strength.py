"""板块维度：强势行业成分股加分。

dimensions 侧仅负责取数入口；打分与 reason 在 engine.dimensions.sector_strength。
"""

from __future__ import annotations

from vnpy_ashare.screener.dimensions.base import DimensionHit, load_quote_snapshot_for_dimension


def run_sector_strength(pool_size: int, *, weight: float) -> tuple[list[DimensionHit], int]:
    from vnpy_ashare.screener.engine.dimensions.sector_strength import run_sector_strength_polars

    loaded = load_quote_snapshot_for_dimension()
    if loaded is None:
        return [], 0
    rows, total = loaded
    return run_sector_strength_polars(rows, pool_size=pool_size, weight=weight, total=total)
