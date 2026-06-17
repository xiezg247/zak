"""本地日 K 健康检查领域模型。"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum

from pydantic import Field

from vnpy_common.domain.base import FrozenModel


class BarHealthStatus(str, Enum):
    """日 K 健康状态。"""

    OK = "ok"
    STALE = "stale"
    GAPS = "gaps"
    UNKNOWN = "unknown"


class BarMeta(FrozenModel):
    """本地 K 线元数据（起止日期与条数）。"""

    start: datetime = Field(description="开始日期")
    end: datetime = Field(description="结束日期")
    count: int = Field(description="数量")


class GapRange(FrozenModel):
    """连续缺失交易日区间。"""

    start: date = Field(description="开始日期")
    end: date = Field(description="结束日期")
    missing_days: int = Field(description="缺失交易日数")


class BarGapResult(FrozenModel):
    """断层扫描结果（含期望/实际交易日数）。"""

    status: BarHealthStatus = Field(description="状态")
    gaps: list[GapRange] = Field(description="断层列表")
    expected_days: int = Field(description="期望交易日数")
    actual_days: int = Field(description="实际覆盖交易日数")
