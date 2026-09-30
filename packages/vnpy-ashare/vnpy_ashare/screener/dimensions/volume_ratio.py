"""量比维度入口（实现见 engine.dimensions.volume_ratio）。"""

from __future__ import annotations

from vnpy_ashare.screener.dimensions.base import DimensionHit, load_quote_snapshot_for_dimension
from vnpy_ashare.screener.engine.dimensions.volume_ratio import run_volume_ratio_pipeline

__all__ = ["run_volume_ratio"]


def run_volume_ratio(pool_size: int, *, weight: float) -> tuple[list[DimensionHit], int]:
    loaded = load_quote_snapshot_for_dimension()
    if loaded is None:
        return run_volume_ratio_pipeline(None, 0, pool_size, weight=weight)
    rows, total = loaded
    return run_volume_ratio_pipeline(rows, total, pool_size, weight=weight)
