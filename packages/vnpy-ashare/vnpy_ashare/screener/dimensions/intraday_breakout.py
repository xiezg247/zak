"""盘中突破维度入口（实现见 engine.dimensions.intraday_breakout）。"""

from __future__ import annotations

from vnpy_ashare.screener.dimensions.base import DimensionHit, load_quote_snapshot_for_dimension
from vnpy_ashare.screener.engine.dimensions.intraday_breakout import (
    breakout_lookback_days,
    minute_confirm_enabled,
    quote_breakout_strength,
    run_intraday_breakout_pipeline,
)

# 兼容旧测例私有名
_breakout_lookback_days = breakout_lookback_days
_minute_confirm_enabled = minute_confirm_enabled
_quote_breakout_strength = quote_breakout_strength

__all__ = [
    "run_intraday_breakout",
    "quote_breakout_strength",
    "_breakout_lookback_days",
    "_minute_confirm_enabled",
    "_quote_breakout_strength",
]


def run_intraday_breakout(pool_size: int, *, weight: float) -> tuple[list[DimensionHit], int]:
    loaded = load_quote_snapshot_for_dimension()
    if loaded is None:
        return [], 0
    rows, total = loaded
    return run_intraday_breakout_pipeline(rows, total, pool_size, weight=weight)
