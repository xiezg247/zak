"""sentiment_gate 元维度入口（不产出命中）。"""

from __future__ import annotations

from vnpy_ashare.screener.dimensions.base import DimensionHit


def run_sentiment_gate(pool_size: int, *, weight: float) -> tuple[list[DimensionHit], int]:
    _ = pool_size, weight
    return [], 0
