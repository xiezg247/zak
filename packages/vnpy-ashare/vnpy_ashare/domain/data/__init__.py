"""K 线数据领域模型。"""

from vnpy_ashare.domain.data.bar import PeriodBarOverview
from vnpy_ashare.domain.data.bar_health import BarGapResult, BarHealthStatus, BarMeta, GapRange

__all__ = [
    "BarGapResult",
    "BarHealthStatus",
    "BarMeta",
    "GapRange",
    "PeriodBarOverview",
]
