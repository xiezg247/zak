"""隔日退出规则领域模型。"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from vnpy_common.domain.base import FrozenModel

ExitSignal = Literal["buy", "sell", "hold", "na"]
RuleStatus = Literal["triggered", "near", "clear"]


class ExitRuleHit(FrozenModel):
    rule_id: str = Field(description="规则 ID")
    label: str = Field(description="展示标签")
    status: RuleStatus = Field(description="状态")
    detail: str = Field(description="详情说明")


class OvernightExitEvaluation(FrozenModel):
    signal: ExitSignal = Field(description="退出信号")
    ref_sell_price: float | None = Field(description="参考卖出价")
    rules: tuple[ExitRuleHit, ...] = Field(description="规则列表")
    warnings: tuple[str, ...] = Field(description="风险提示列表")
    reasons: tuple[str, ...] = Field(description="理由")
