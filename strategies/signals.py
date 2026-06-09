"""策略信号纯函数（与 CTA 策略逻辑对齐，不依赖回测引擎）。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Literal

SignalType = Literal["golden_cross", "death_cross"]


@dataclass(frozen=True)
class CrossSignal:
    signal_type: SignalType
    bar_date: str
    close: float
    fast_ma: float
    slow_ma: float


def _sma(values: list[float], window: int, end_index: int) -> float | None:
    if end_index + 1 < window:
        return None
    segment = values[end_index + 1 - window : end_index + 1]
    return sum(segment) / len(segment)


def compute_double_ma_crosses(
    closes: list[float],
    dates: list[date | datetime],
    *,
    fast_window: int = 10,
    slow_window: int = 20,
) -> list[CrossSignal]:
    """扫描全序列，返回金叉/死叉事件（与 AshareDoubleMaStrategy 判定一致）。"""
    if fast_window >= slow_window:
        raise ValueError("fast_window 必须小于 slow_window")
    if len(closes) != len(dates):
        raise ValueError("closes 与 dates 长度不一致")
    if len(closes) < slow_window + 2:
        return []

    signals: list[CrossSignal] = []
    for index in range(slow_window + 1, len(closes)):
        fast_ma0 = _sma(closes, fast_window, index)
        fast_ma1 = _sma(closes, fast_window, index - 1)
        slow_ma0 = _sma(closes, slow_window, index)
        slow_ma1 = _sma(closes, slow_window, index - 1)
        if None in (fast_ma0, fast_ma1, slow_ma0, slow_ma1):
            continue

        cross_over = fast_ma0 > slow_ma0 and fast_ma1 <= slow_ma1
        cross_below = fast_ma0 < slow_ma0 and fast_ma1 >= slow_ma1
        bar_dt = dates[index]
        bar_date = bar_dt.strftime("%Y-%m-%d") if isinstance(bar_dt, datetime) else bar_dt.isoformat()
        close = round(closes[index], 2)

        if cross_over:
            signals.append(
                CrossSignal(
                    signal_type="golden_cross",
                    bar_date=bar_date,
                    close=close,
                    fast_ma=round(fast_ma0, 2),
                    slow_ma=round(slow_ma0, 2),
                )
            )
        elif cross_below:
            signals.append(
                CrossSignal(
                    signal_type="death_cross",
                    bar_date=bar_date,
                    close=close,
                    fast_ma=round(fast_ma0, 2),
                    slow_ma=round(slow_ma0, 2),
                )
            )
    return signals


def summarize_double_ma_state(
    closes: list[float],
    dates: list[date | datetime],
    *,
    fast_window: int = 10,
    slow_window: int = 20,
    recent_limit: int = 5,
) -> dict[str, Any]:
    """汇总当前均线状态与最近交叉信号。"""
    if len(closes) < slow_window + 2:
        return {
            "error": "K 线数量不足，无法计算双均线信号",
            "min_bars": slow_window + 2,
            "bars_available": len(closes),
        }

    last_index = len(closes) - 1
    fast_ma0 = _sma(closes, fast_window, last_index)
    fast_ma1 = _sma(closes, fast_window, last_index - 1)
    slow_ma0 = _sma(closes, slow_window, last_index)
    _ = _sma(closes, slow_window, last_index - 1)
    assert fast_ma0 is not None and slow_ma0 is not None

    if fast_ma0 > slow_ma0:
        alignment = "快线在慢线上方（多头均线排列）"
    elif fast_ma0 < slow_ma0:
        alignment = "快线在慢线下方（空头均线排列）"
    else:
        alignment = "快线与慢线重合"

    last_dt = dates[last_index]
    as_of = last_dt.strftime("%Y-%m-%d") if isinstance(last_dt, datetime) else last_dt.isoformat()

    crosses = compute_double_ma_crosses(
        closes,
        dates,
        fast_window=fast_window,
        slow_window=slow_window,
    )
    last_cross = crosses[-1] if crosses else None
    recent = crosses[-recent_limit:] if crosses else []

    last_cross_payload: dict[str, Any] | None = None
    if last_cross is not None:
        last_cross_payload = {
            "type": last_cross.signal_type,
            "type_label": "金叉" if last_cross.signal_type == "golden_cross" else "死叉",
            "date": last_cross.bar_date,
            "close": last_cross.close,
            "fast_ma": last_cross.fast_ma,
            "slow_ma": last_cross.slow_ma,
        }

    return {
        "as_of": as_of,
        "last_close": round(closes[last_index], 2),
        "params": {"fast_window": fast_window, "slow_window": slow_window},
        "current": {
            "fast_ma": round(fast_ma0, 2),
            "slow_ma": round(slow_ma0, 2),
            "alignment": alignment,
            "fast_slope": round(fast_ma0 - (fast_ma1 or fast_ma0), 4),
        },
        "last_cross": last_cross_payload,
        "recent_signals": [
            {
                "type": item.signal_type,
                "type_label": "金叉" if item.signal_type == "golden_cross" else "死叉",
                "date": item.bar_date,
                "close": item.close,
                "fast_ma": item.fast_ma,
                "slow_ma": item.slow_ma,
            }
            for item in recent
        ],
        "signal_count": len(crosses),
    }


SUPPORTED_SIGNAL_STRATEGIES: dict[str, str] = {
    "AshareDoubleMaStrategy": "double_ma",
}


def list_supported_signal_strategies() -> list[str]:
    return sorted(SUPPORTED_SIGNAL_STRATEGIES.keys())
