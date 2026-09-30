"""盘中资金维度入口（实现见 moneyflow_resolve）。"""

from __future__ import annotations

from vnpy_ashare.screener.dimensions.base import DimensionHit
from vnpy_ashare.screener.dimensions.moneyflow_resolve import resolve_moneyflow_hits

__all__ = ["run_moneyflow_intraday"]


def run_moneyflow_intraday(pool_size: int, *, weight: float) -> tuple[list[DimensionHit], int]:
    hits, total, _ = resolve_moneyflow_hits(pool_size, weight=weight)
    return hits, total
