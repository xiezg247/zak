"""个股分析概览仪表盘领域模型。"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from vnpy_common.domain.base import FrozenModel, MutableModel

ReadinessStatus = Literal["ready", "partial", "missing", "unconfigured"]
OverviewJumpTarget = Literal["chart", "short_term", "sector", "capital", "events", "holders", "financial"]
AlertSeverity = Literal["info", "warn"]


class DataReadinessItem(FrozenModel):
    key: str = Field(description="键名")
    label: str = Field(description="展示标签")
    status: ReadinessStatus = Field(description="状态")
    detail: str = Field(default="", description="详情说明")
    jump_target: OverviewJumpTarget | None = Field(default=None, description="跳转 Tab")


class OverviewAlert(FrozenModel):
    text: str = Field(description="文本内容")
    severity: AlertSeverity = Field(default="info", description="严重级别")
    jump_target: OverviewJumpTarget | None = Field(default=None, description="跳转 Tab")


class ScreeningHit(FrozenModel):
    condition: str = Field(description="条件")
    rank: int = Field(description="排名")
    total: int = Field(description="总数")
    updated_at: str | None = Field(default=None, description="更新时间")


class OverviewDashboard(MutableModel):
    readiness: list[DataReadinessItem] = Field(default_factory=list, description="数据就绪项")
    alerts: list[OverviewAlert] = Field(default_factory=list, description="关键提醒")
    screening: ScreeningHit | None = Field(default=None, description="选股命中上下文")
