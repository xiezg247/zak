"""估值维度：行业相对低 PE 排行。"""

from __future__ import annotations

from vnpy_ashare.screener.data.data_source import fetch_fundamental_screening_rows
from vnpy_ashare.screener.dimensions.base import DimensionHit


def run_low_pe(pool_size: int, *, weight: float) -> tuple[list[DimensionHit], int]:
    from vnpy_ashare.screener.engine.dimensions.low_pe import run_low_pe_polars

    raw_rows, _trade_date, _ = fetch_fundamental_screening_rows()
    if not raw_rows:
        return [], 0

    result = run_low_pe_polars(raw_rows, pool_size=pool_size, weight=weight)
    if result is not None:
        return result
    return [], len(raw_rows)
