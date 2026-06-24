"""持仓与交易参数只读指标。"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from vnpy_ashare.config.preferences.trading_risk import load_trading_risk_prefs

if TYPE_CHECKING:
    from vnpy_ashare.domain.trading.position import PositionSnapshot

__all__ = [
    "compute_avg_float_pnl_pct",
    "format_emotion_position_hint",
    "read_total_capital",
]


def read_total_capital() -> float | None:
    return load_trading_risk_prefs().total_capital


def compute_avg_float_pnl_pct(
    position_cache: Mapping[str, PositionSnapshot] | None,
) -> float | None:
    if not position_cache:
        return None
    pnls = [snap.unrealized_pnl_pct for snap in position_cache.values() if snap.unrealized_pnl_pct is not None]
    if not pnls:
        return None
    return sum(pnls) / len(pnls)


def format_emotion_position_hint(
    *,
    position_pct_min: float | None,
    position_pct_max: float | None,
) -> str | None:
    if position_pct_max is None:
        return None
    pos_max = int(position_pct_max * 100)
    if position_pct_min is not None and position_pct_min > 0:
        pos_min = int(position_pct_min * 100)
        return f"情绪建议 {pos_min}–{pos_max}%"
    return f"情绪建议 ≤{pos_max}%"
