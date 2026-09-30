"""维度执行共用类型与工具（兼容入口）。

类型来自 domain；hit 组装 / 快照加载见 engine.dimensions.hits。
"""

from __future__ import annotations

from vnpy_ashare.domain.screener.dimension_hit import DimensionHit, dimension_hit_row
from vnpy_ashare.screener.engine.dimensions.hits import (
    fundamental_base_row,
    load_quote_snapshot_for_dimension,
    merge_rows,
    quote_hits,
)
from vnpy_ashare.screener.engine.dimensions.scoring import rank_score

__all__ = [
    "DimensionHit",
    "dimension_hit_row",
    "fundamental_base_row",
    "load_quote_snapshot_for_dimension",
    "merge_rows",
    "quote_hits",
    "rank_score",
]
