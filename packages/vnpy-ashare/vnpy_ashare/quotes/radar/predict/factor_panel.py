"""雷达预测因子面板（训练与推理共用）。"""

from __future__ import annotations

import math
from typing import Any

FEATURE_NAMES: tuple[str, ...] = (
    "ret_1d",
    "ret_5d",
    "ret_20d",
    "volume_ratio_5d",
    "volatility_20d",
    "turnover_rate",
)


def _safe_return(closes: list[float], end_index: int, lookback: int) -> float | None:
    start_index = end_index - lookback
    if start_index < 0:
        return None
    start = closes[start_index]
    end = closes[end_index]
    if start <= 0:
        return None
    return (end - start) / start


def _daily_volatility(closes: list[float], end_index: int, window: int = 20) -> float | None:
    start = max(1, end_index - window + 1)
    returns: list[float] = []
    for index in range(start, end_index + 1):
        prev = closes[index - 1]
        cur = closes[index]
        if prev <= 0:
            continue
        returns.append((cur - prev) / prev)
    if len(returns) < 5:
        return None
    mean_ret = sum(returns) / len(returns)
    variance = sum((value - mean_ret) ** 2 for value in returns) / len(returns)
    return math.sqrt(variance) * 100.0


def features_from_bar_window(
    closes: list[float],
    volumes: list[float],
    *,
    end_index: int,
    turnover_rate: float = 0.0,
) -> dict[str, float] | None:
    if end_index < 0 or end_index >= len(closes):
        return None
    ret_1d = _safe_return(closes, end_index, 1)
    ret_5d = _safe_return(closes, end_index, 5)
    ret_20d = _safe_return(closes, end_index, 20)
    vol_ratio = 1.0
    if end_index >= 5 and len(volumes) == len(closes):
        tail = volumes[max(0, end_index - 4) : end_index + 1]
        avg_vol = sum(float(value) for value in tail[:-1]) / max(len(tail) - 1, 1)
        last_vol = float(tail[-1])
        if avg_vol > 0:
            vol_ratio = last_vol / avg_vol
    volatility = _daily_volatility(closes, end_index)
    if ret_1d is None or ret_5d is None or ret_20d is None or volatility is None:
        return None
    return {
        "ret_1d": round(ret_1d * 100.0, 4),
        "ret_5d": round(ret_5d * 100.0, 4),
        "ret_20d": round(ret_20d * 100.0, 4),
        "volume_ratio_5d": round(vol_ratio, 4),
        "volatility_20d": round(volatility, 4),
        "turnover_rate": round(float(turnover_rate or 0.0), 4),
    }


def features_from_quote_row(row: dict[str, Any]) -> dict[str, float]:
    """推理时优先用行情字段；缺省由模型 manifest 中位数填充。"""
    change = float(row.get("change_pct") or row.get("pct_chg") or 0.0)
    return {
        "ret_1d": round(change, 4),
        "ret_5d": round(float(row.get("ret_5d") or change), 4),
        "ret_20d": round(float(row.get("ret_20d") or change), 4),
        "volume_ratio_5d": round(float(row.get("volume_ratio") or row.get("volume_ratio_5d") or 1.0), 4),
        "volatility_20d": round(float(row.get("volatility_20d") or 2.0), 4),
        "turnover_rate": round(float(row.get("turnover_rate") or 0.0), 4),
    }


def feature_vector(features: dict[str, float], *, feature_names: tuple[str, ...] = FEATURE_NAMES) -> list[float]:
    return [float(features.get(name, 0.0)) for name in feature_names]
