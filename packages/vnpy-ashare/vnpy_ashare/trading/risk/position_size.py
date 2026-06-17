"""单笔风险仓位计算器（K-02）。"""

from __future__ import annotations

from typing import Any

from pydantic import Field

from vnpy_ashare.config.preferences.trading_risk import (
    DEFAULT_PER_TRADE_RISK_PCT,
    DEFAULT_STOP_LOSS_PCT,
    load_trading_risk_prefs,
)
from vnpy_ashare.domain.base import FrozenModel


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


def compute_position_size(
    *,
    total_capital: float,
    cost_price: float,
    stop_loss_pct: float = DEFAULT_STOP_LOSS_PCT,
    per_trade_risk_pct: float = DEFAULT_PER_TRADE_RISK_PCT,
    requested_volume: int | None = None,
) -> PositionSizeResult | None:
    if total_capital <= 0 or cost_price <= 0 or stop_loss_pct <= 0 or per_trade_risk_pct <= 0:
        return None
    max_loss_amount = total_capital * per_trade_risk_pct
    loss_per_share = cost_price * stop_loss_pct
    if loss_per_share <= 0:
        return None
    raw_shares = max_loss_amount / loss_per_share
    max_shares = max(0, int(raw_shares // 100) * 100)
    exceeds: bool | None = None
    if requested_volume is not None and max_shares > 0:
        exceeds = requested_volume > max_shares
    return PositionSizeResult(
        max_shares=max_shares,
        max_loss_amount=max_loss_amount,
        per_trade_risk_pct=per_trade_risk_pct,
        stop_loss_pct=stop_loss_pct,
        cost_price=cost_price,
        total_capital=total_capital,
        volume_exceeds_suggestion=exceeds,
        requested_volume=requested_volume,
    )


def compute_position_size_from_prefs(
    *,
    cost_price: float,
    requested_volume: int | None = None,
    stop_loss_pct: float | None = None,
    per_trade_risk_pct: float | None = None,
) -> PositionSizeResult | None:
    prefs = load_trading_risk_prefs()
    if prefs.total_capital is None:
        return None
    return compute_position_size(
        total_capital=prefs.total_capital,
        cost_price=cost_price,
        stop_loss_pct=stop_loss_pct if stop_loss_pct is not None else prefs.stop_loss_pct,
        per_trade_risk_pct=per_trade_risk_pct if per_trade_risk_pct is not None else prefs.per_trade_risk_pct,
        requested_volume=requested_volume,
    )


def format_position_size_hint(result: PositionSizeResult | None) -> str:
    if result is None:
        return "请在「风控设置」填写总资金后显示单笔建议股数"
    if result.max_shares <= 0:
        return "按当前成本与止损比例，单笔 2% 风控建议 0 股"
    risk_pct = int(result.per_trade_risk_pct * 100)
    stop_pct = int(result.stop_loss_pct * 100)
    text = f"按 {risk_pct}% 风控、止损 {stop_pct}% 建议 ≤ {result.max_shares:,} 股"
    if result.volume_exceeds_suggestion:
        text += "（当前持仓量超出建议）"
    return text
