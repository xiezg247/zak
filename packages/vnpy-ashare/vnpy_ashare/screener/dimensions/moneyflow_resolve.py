"""资金流命中统一解析入口（实现见 engine.dimensions.moneyflow_resolve）。"""

from __future__ import annotations

from vnpy_ashare.screener.engine.dimensions.moneyflow_resolve import (
    build_moneyflow_source_subtitle,
    count_positive_moneyflow_streak,
    moneyflow_score_adjustment,
    resolve_moneyflow_hits,
)

# 兼容旧测例私有名
_moneyflow_score_adjustment = moneyflow_score_adjustment

__all__ = [
    "build_moneyflow_source_subtitle",
    "count_positive_moneyflow_streak",
    "moneyflow_score_adjustment",
    "resolve_moneyflow_hits",
    "_moneyflow_score_adjustment",
]
