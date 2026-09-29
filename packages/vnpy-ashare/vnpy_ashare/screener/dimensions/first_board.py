"""首板人气维度：limit_times=1 + 封板时间代理。

dimensions 侧仅负责取数入口；打分与 reason 在 engine.dimensions.first_board。
"""

from __future__ import annotations

from vnpy_ashare.screener.dimensions.base import DimensionHit, load_quote_snapshot_for_dimension


def run_first_board(pool_size: int, *, weight: float) -> tuple[list[DimensionHit], int]:
    from vnpy_ashare.screener.engine.dimensions.first_board import run_first_board_polars

    loaded = load_quote_snapshot_for_dimension()
    if loaded is None:
        return [], 0
    rows, total = loaded
    return run_first_board_polars(rows, pool_size=pool_size, weight=weight, total=total)
