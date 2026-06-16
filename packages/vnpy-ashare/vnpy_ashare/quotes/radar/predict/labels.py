"""雷达预测标签（仅训练使用）。"""

from __future__ import annotations


def forward_return_pct(closes: list[float], *, index: int, horizon: int) -> float | None:
    target = index + horizon
    if target >= len(closes):
        return None
    start = closes[index]
    end = closes[target]
    if start <= 0:
        return None
    return round((end - start) / start * 100.0, 4)


def forward_direction_label(closes: list[float], *, index: int, horizon: int) -> int | None:
    ret = forward_return_pct(closes, index=index, horizon=horizon)
    if ret is None:
        return None
    return 1 if ret > 0 else 0
