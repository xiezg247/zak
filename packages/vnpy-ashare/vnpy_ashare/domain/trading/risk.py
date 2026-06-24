"""交易风控领域模型。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from vnpy_ashare.domain.market.emotion import EmotionCycleSnapshot
from vnpy_common.domain.base import FrozenModel

RiskGateState = Literal["normal", "caution", "halt"]


class RiskGateSnapshot(FrozenModel):
    state: RiskGateState = Field(description="风控闸状态")
    state_label: str = Field(description="风控闸状态中文标签")
    allow_new_positions: bool = Field(description="是否允许新开仓")
    daily_pnl_pct: float | None = Field(description="当日盈亏占比（%）")
    avg_float_pnl_pct: float | None = Field(description="持仓平均浮盈占比（%）")
    weekly_drawdown_pct: float | None = Field(default=None, description="单周回撤（%）")
    total_drawdown_pct: float | None = Field(default=None, description="总回撤（%）")
    halt_until: str | None = Field(default=None, description="定时熔断截止日")
    warnings: tuple[str, ...] = Field(description="风险提示列表")


class CombinedRiskGateSnapshot(FrozenModel):
    account: RiskGateSnapshot = Field(description="账户风控闸快照")
    emotion: EmotionCycleSnapshot | None = Field(description="情绪周期快照")
    allow_new_positions: bool = Field(description="是否允许新开仓")
    emotion_position_pct_min: float | None = Field(description="情绪建议仓位下限（0–1）")
    emotion_position_pct_max: float | None = Field(description="情绪建议仓位上限（0–1）")
    actual_position_pct: float | None = Field(description="实际仓位占比（0–1）")
    total_capital: float | None = Field(description="总资金")
    warnings: tuple[str, ...] = Field(description="风险提示列表")

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "allow_new_positions": self.allow_new_positions,
            "account": {
                "state": self.account.state,
                "state_label": self.account.state_label,
                "allow_new_positions": self.account.allow_new_positions,
                "daily_pnl_pct": self.account.daily_pnl_pct,
                "avg_float_pnl_pct": self.account.avg_float_pnl_pct,
                "weekly_drawdown_pct": self.account.weekly_drawdown_pct,
                "total_drawdown_pct": self.account.total_drawdown_pct,
                "halt_until": self.account.halt_until,
                "warnings": list(self.account.warnings),
            },
            "warnings": list(self.warnings),
        }
        if self.emotion is not None:
            payload["emotion"] = {
                "stage": self.emotion.stage,
                "stage_label": self.emotion.stage_label,
                "position_pct_min": self.emotion.position_pct_min,
                "position_pct_max": self.emotion.position_pct_max,
                "allow_new_positions": self.emotion.allow_new_positions,
            }
        if self.emotion_position_pct_min is not None:
            payload["emotion_position_pct_min"] = self.emotion_position_pct_min
        if self.emotion_position_pct_max is not None:
            payload["emotion_position_pct_max"] = self.emotion_position_pct_max
        if self.actual_position_pct is not None:
            payload["actual_position_pct"] = self.actual_position_pct
        if self.total_capital is not None:
            payload["total_capital"] = self.total_capital
        return payload


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


class PositionSizeResult(FrozenModel):
    max_shares: int = Field(description="单笔建议最大股数")
    max_loss_amount: float = Field(description="单笔最大亏损金额")
    per_trade_risk_pct: float = Field(description="单笔风险占比（0–1）")
    stop_loss_pct: float = Field(description="止损比例（0–1）")
    cost_price: float = Field(description="成本价")
    total_capital: float = Field(description="总资金")
    volume_exceeds_suggestion: bool | None = Field(default=None, description="请求股数是否超出建议")
    requested_volume: int | None = Field(default=None, description="请求买入股数")

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "max_shares": self.max_shares,
            "max_loss_amount": round(self.max_loss_amount, 2),
            "per_trade_risk_pct": self.per_trade_risk_pct,
            "stop_loss_pct": self.stop_loss_pct,
            "cost_price": self.cost_price,
            "total_capital": self.total_capital,
        }
        if self.volume_exceeds_suggestion is not None:
            payload["volume_exceeds_suggestion"] = self.volume_exceeds_suggestion
        if self.requested_volume is not None:
            payload["requested_volume"] = self.requested_volume
        return payload
