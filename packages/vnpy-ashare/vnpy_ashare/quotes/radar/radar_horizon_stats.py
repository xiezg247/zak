"""雷达未来展望扫描统计（轻量类型，避免 radar_horizon_scan 循环依赖）。"""

from __future__ import annotations

from pydantic import Field

from vnpy_common.domain.base import FrozenModel


class HorizonScanStats(FrozenModel):
    scanned_total: int = Field(description="全市场扫描总数")
    excluded_count: int = Field(description="排除标的数")
    prefilter_total: int = Field(description="粗筛池数量")
    refined_total: int = Field(description="精算数量")
    kline_missing: int = Field(description="日 K 缺失数量")
