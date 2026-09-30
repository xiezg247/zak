"""动量维度入口（实现见 engine.dimensions.momentum）。"""

from __future__ import annotations

from vnpy_ashare.screener.dimensions.base import DimensionHit, load_quote_snapshot_for_dimension
from vnpy_ashare.screener.engine.dimensions.momentum import (
    momentum_reason,
    run_momentum_from_fundamentals,
    run_momentum_from_rows,
)

__all__ = ["run_momentum", "momentum_reason"]


def run_momentum(pool_size: int, *, weight: float) -> tuple[list[DimensionHit], int]:
    loaded = load_quote_snapshot_for_dimension()
    if loaded is None:
        return run_momentum_from_fundamentals(pool_size, weight=weight)
    rows, total = loaded
    return run_momentum_from_rows(rows, total, pool_size, weight=weight)
