"""放量维度：相对成交量（量比 / 成交额）排行。

dimensions 侧仅负责取数入口；打分与 reason 在 engine.dimensions.volume_surge。
"""

from __future__ import annotations

from vnpy_ashare.screener.dimensions.base import DimensionHit, load_quote_snapshot_for_dimension


def run_volume_surge(pool_size: int, *, weight: float) -> tuple[list[DimensionHit], int]:
    from vnpy_ashare.screener.engine.dimensions.volume_surge import run_volume_surge_polars

    loaded = load_quote_snapshot_for_dimension()
    if loaded is None:
        return [], 0
    rows, total = loaded
    return run_volume_surge_polars(rows, pool_size=pool_size, weight=weight, total=total)
