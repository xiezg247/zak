"""盘中突破维度入口（实现见 engine.dimensions.intraday_breakout）。"""

from __future__ import annotations

from vnpy_ashare.screener.engine.dimensions.intraday_breakout import (
    breakout_lookback_days,
    minute_confirm_enabled,
    quote_breakout_strength,
    run_intraday_breakout,
)

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
