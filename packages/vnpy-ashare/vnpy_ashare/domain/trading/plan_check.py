"""交易计划校验领域模型。"""

from __future__ import annotations

from pydantic import Field

from vnpy_common.domain.base import FrozenModel


class BuyPlanCheckResult(FrozenModel):
    on_plan: bool = Field(description="是否在交易计划内")
    plan_id: str | None = Field(description="交易计划 ID")
    plan_trade_date: str | None = Field(description="计划交易日")
    violation_tags: tuple[str, ...] = Field(description="违规标签")
    warnings: tuple[str, ...] = Field(description="风险提示列表")

    @property
    def has_violations(self) -> bool:
        return bool(self.violation_tags)
