"""盘中资金维度：优先 TDX MCP 主力净流入，不可用时成交额+涨幅代理。"""

from __future__ import annotations

from vnpy_ashare.screener.dimensions.base import DimensionHit
from vnpy_ashare.screener.dimensions.moneyflow_resolve import resolve_moneyflow_hits


def run_moneyflow_intraday(pool_size: int, *, weight: float) -> tuple[list[DimensionHit], int]:
    hits, total, _ = resolve_moneyflow_hits(pool_size, weight=weight)
    return hits, total
