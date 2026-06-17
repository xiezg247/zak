"""雷达预测扫描领域模型。"""

from __future__ import annotations

from pydantic import Field

from vnpy_ashare.domain.radar.card import RadarRow
from vnpy_ashare.domain.radar.horizon import HorizonScanStats
from vnpy_common.domain.base import FrozenModel


class PredictScanResult(FrozenModel):
    variant: str = Field(description="变体标识")
    rows: tuple[RadarRow, ...] = Field(description="数据行列表")
    stats: HorizonScanStats = Field(description="扫描统计")
    model_label: str = Field(description="模型标签")
    computed_at: str = Field(description="计算时间")


class PredictCacheEntry(FrozenModel):
    variant: str = Field(description="变体标识")
    rows: tuple[RadarRow, ...] = Field(description="数据行列表")
    stats: HorizonScanStats = Field(description="扫描统计")
    model_label: str = Field(description="模型标签")
    computed_at: str = Field(description="计算时间")
