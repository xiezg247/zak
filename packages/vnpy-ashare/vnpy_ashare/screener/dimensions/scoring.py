"""维度得分（兼容入口；实现见 engine.dimensions.scoring）。"""

from __future__ import annotations

from vnpy_ashare.screener.engine.dimensions.scoring import (
    blended_score,
    metric_percentile,
    metric_score_blend,
    rank_score,
    relative_ratio,
)

__all__ = [
    "blended_score",
    "metric_percentile",
    "metric_score_blend",
    "rank_score",
    "relative_ratio",
]
