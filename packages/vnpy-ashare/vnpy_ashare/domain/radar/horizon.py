"""雷达未来展望扫描领域模型。"""

from __future__ import annotations

from pydantic import Field

from vnpy_ashare.domain.radar.card import RadarRow
from vnpy_common.domain.base import FrozenModel


class HorizonScanStats(FrozenModel):
    scanned_total: int = Field(description="全市场扫描总数")
    excluded_count: int = Field(description="排除标的数")
    prefilter_total: int = Field(description="粗筛池数量")
    refined_total: int = Field(description="精算数量")
    kline_missing: int = Field(description="日 K 缺失数量")


class HorizonScanResult(FrozenModel):
    variant: str = Field(description="变体标识")
    rows: tuple[RadarRow, ...] = Field(description="数据行列表")
    stats: HorizonScanStats = Field(description="扫描统计")
    strategy_key: str = Field(description="策略配置键")
    computed_at: str = Field(description="计算时间")
