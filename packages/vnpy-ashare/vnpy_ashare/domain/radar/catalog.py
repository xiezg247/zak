"""雷达页卡片注册领域模型。"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from vnpy_common.domain.base import FrozenModel

RadarCategory = Literal["screen", "discovery", "watchlist", "sector", "outlook"]
RadarCardMode = Literal["statistical", "predictive"]


class RadarRefreshOption(FrozenModel):
    ms: int = Field(description="刷新间隔（毫秒）")
    label: str = Field(description="展示标签")


class RadarLayoutSection(FrozenModel):
    mode: RadarCardMode = Field(description="模式")
    title: str = Field(description="标题")
    hint: str = Field(description="提示文案")


class RadarCardSpec(FrozenModel):
    id: str = Field(description="主键 ID")
    title: str = Field(description="标题")
    category: RadarCategory = Field(description="分类")
    mode: RadarCardMode = Field(default="statistical", description="卡片模式")
    top_n: int = Field(default=8, description="展示条数")
    has_task_variants: bool = Field(default=False, description="是否有任务变体")
    auto_refresh_ms: int | None = Field(default=None, description="自动刷新间隔（毫秒）")


class RadarVariant(FrozenModel):
    key: str = Field(description="键名")
    label: str = Field(description="展示标签")
