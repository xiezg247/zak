"""选股维度共用的日线历史信号（兼容入口；实现见 engine）。"""

from __future__ import annotations

from vnpy_ashare.screener.engine.dimensions.history_signals import (
    attach_momentum_persistence,
    bars_for_vt_symbol,
    breaks_rolling_high,
    history_lookback_bars,
    load_history_bars_map,
    momentum_persistence_score_factor,
    positive_close_streak,
    positive_day_count,
    rolling_high_before_last,
)

__all__ = [
    "attach_momentum_persistence",
    "bars_for_vt_symbol",
    "breaks_rolling_high",
    "history_lookback_bars",
    "load_history_bars_map",
    "momentum_persistence_score_factor",
    "positive_close_streak",
    "positive_day_count",
    "rolling_high_before_last",
]
