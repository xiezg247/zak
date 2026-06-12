"""常用技术指标纯函数。"""

from __future__ import annotations

import math


def calc_ema(values: list[float], period: int) -> list[float]:
    if period <= 0 or not values:
        return []
    alpha = 2.0 / (period + 1)
    result: list[float] = []
    ema = values[0]
    result.append(ema)
    for value in values[1:]:
        ema = alpha * value + (1 - alpha) * ema
        result.append(ema)
    return result


def calc_macd(
    closes: list[float],
    *,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> tuple[list[float], list[float], list[float]]:
    """返回 DIF、DEA、MACD 柱（(DIF-DEA)*2）序列，长度与 closes 一致。"""
    size = len(closes)
    if size == 0:
        return [], [], []

    ema_fast = calc_ema(closes, fast)
    ema_slow = calc_ema(closes, slow)
    dif = [fast_v - slow_v for fast_v, slow_v in zip(ema_fast, ema_slow, strict=False)]
    dea = calc_ema(dif, signal)
    hist = [(d - e) * 2 for d, e in zip(dif, dea, strict=False)]

    warmup = slow + signal
    for idx in range(min(warmup, size)):
        dif[idx] = math.nan
        dea[idx] = math.nan
        hist[idx] = math.nan
    return dif, dea, hist
