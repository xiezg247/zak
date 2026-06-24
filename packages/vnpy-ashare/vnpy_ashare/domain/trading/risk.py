"""交易盈亏与仓位汇总领域模型。"""

from __future__ import annotations

from pydantic import Field

from vnpy_common.domain.base import FrozenModel


class BookPnlSummary(FrozenModel):
    total_float_pnl: float = Field(description="浮动盈亏合计")
    position_count: int = Field(description="持仓数量")
    total_float_pnl_pct: float | None = Field(description="浮动盈亏占比（%）")
    avg_float_pnl_pct: float | None = Field(description="持仓平均浮盈占比（%）")
    realized_pnl_today: float | None = Field(description="当日已实现盈亏")
    combined_pnl_amount: float | None = Field(description="合计盈亏金额")
    combined_pnl_pct: float | None = Field(description="合计盈亏占比（%）")


class GroupPositionSummary(FrozenModel):
    group_id: str = Field(description="分组 ID")
    position_count: int = Field(description="持仓数量")
    actual_pct: float | None = Field(description="实际仓位占比（0–1）")
    plan_cap_pct: float | None = Field(description="计划仓位上限（0–1）")
    plan_pct_sum: float | None = Field(description="计划占比合计（0–1）")
    over_cap: bool = Field(description="是否超出上限")
