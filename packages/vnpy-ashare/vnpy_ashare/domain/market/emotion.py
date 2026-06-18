"""情绪周期领域模型。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from vnpy_common.domain.base import FrozenModel

EmotionStage = Literal["ice", "startup", "climax", "divergence", "recession"]
EmotionMode = Literal["limit_board", "halfway", "pullback"]


class EmotionCycleInputs(FrozenModel):
    limit_up_count: int = Field(description="涨停家数")
    limit_down_count: int = Field(description="跌停家数")
    up_ratio: float = Field(description="上涨占比（0–1）")
    total_amount: float = Field(description="成交额合计")
    max_limit_times: int = Field(description="最高连板数")
    limit_ladder_depth: int = Field(description="连板梯队层数")
    index_above_ma5: bool | None = Field(default=None, description="大盘是否在5日均线上方")
    fear_greed_index: float | None = Field(default=None, description="恐贪指数")
    updated_at: str | None = Field(default=None, description="数据更新时间")
    limit_break_rate: float | None = Field(default=None, description="连板断板率（0–1）")
    prev_leader_limit_down: bool = Field(default=False, description="昨最高板今日跌停")
    prev_max_limit_times: int | None = Field(default=None, description="昨最高连板数")


class EmotionCycleSnapshot(FrozenModel):
    stage: EmotionStage = Field(description="情绪阶段")
    stage_label: str = Field(description="阶段中文标签")
    position_pct_min: float = Field(description="建议仓位下限（0–1）")
    position_pct_max: float = Field(description="建议仓位上限（0–1）")
    position_factor: float = Field(description="仓位系数（0–1）")
    allowed_modes: tuple[str, ...] = Field(description="允许的买点模式")
    allow_new_positions: bool = Field(description="是否允许新开仓")
    warnings: tuple[str, ...] = Field(description="风险提示列表")
    inputs: dict[str, Any] = Field(description="判定输入因子")
    updated_at: str = Field(description="更新时间")

    @property
    def limit_up_count(self) -> int:
        return int(self.inputs.get("limit_up_count", 0))

    @property
    def limit_down_count(self) -> int:
        return int(self.inputs.get("limit_down_count", 0))

    @property
    def up_ratio(self) -> float:
        return float(self.inputs.get("up_ratio", 0.0))
