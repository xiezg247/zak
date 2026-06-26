"""放量维度：相对成交量（量比 / 成交额）排行。"""

from __future__ import annotations

from typing import Any

from vnpy_ashare.screener.data.data_source import load_screening_quote_snapshot
from vnpy_ashare.screener.data.quotes_loader import MarketQuotesLoadError
from vnpy_ashare.screener.dimensions.base import DimensionHit
def run_volume_surge(pool_size: int, *, weight: float) -> tuple[list[DimensionHit], int]:
    from vnpy_ashare.screener.engine.dimensions.volume_surge import run_volume_surge_polars

    try:
        snapshot = load_screening_quote_snapshot()
    except MarketQuotesLoadError:
        return [], 0

    return run_volume_surge_polars(
        list(snapshot.rows),
        pool_size=pool_size,
        weight=weight,
        total=snapshot.total,
    )


def _volume_surge_reason(row: dict[str, Any], rank: int) -> str:
    ratio = float(row.get("volume_ratio") or 0)
    relative = float(row.get("relative_volume") or 0)
    if ratio > 0:
        return f"放量：量比 {ratio:.2f}，相对量 {relative:.2f}，排名第 {rank}"
    volume = float(row.get("volume") or 0)
    if volume > 0:
        return f"放量：成交量 {volume:,.0f}，排名第 {rank}"
    amount = float(row.get("amount") or 0)
    return f"放量：成交额 {amount:,.0f}，排名第 {rank}"
