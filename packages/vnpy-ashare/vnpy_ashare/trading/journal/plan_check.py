"""登记买入 vs 交易计划校验（J-04 / K-05）。"""

from __future__ import annotations

from pydantic import Field
from vnpy.trader.constant import Exchange

from vnpy_common.domain.base import FrozenModel
from vnpy_ashare.domain.trading.plan import TradingPlanRecord
from vnpy_ashare.quotes.market.emotion_cycle import load_emotion_cycle_snapshot
from vnpy_ashare.storage.repositories.trading_plans import load_active_trading_plan


class BuyPlanCheckResult(FrozenModel):
    on_plan: bool = Field(description="是否在交易计划内")
    plan_id: str | None = Field(description="交易计划 ID")
    plan_trade_date: str | None = Field(description="计划交易日")
    violation_tags: tuple[str, ...] = Field(description="违规标签")
    warnings: tuple[str, ...] = Field(description="风险提示列表")

    @property
    def has_violations(self) -> bool:
        return bool(self.violation_tags)


def _symbol_on_plan(plan: TradingPlanRecord, symbol: str, exchange: Exchange) -> bool:
    key = (symbol, exchange.name)
    return any((item.symbol, item.exchange) == key for item in plan.symbols)


def check_buy_against_plan(
    symbol: str,
    exchange: Exchange,
    *,
    trade_date: str,
    active_plan: TradingPlanRecord | None = None,
) -> BuyPlanCheckResult:
    plan = active_plan if active_plan is not None else load_active_trading_plan(trade_date)
    emotion = load_emotion_cycle_snapshot(fetch_if_missing=True)
    tags: list[str] = []
    warnings: list[str] = []

    if emotion is not None and emotion.stage == "recession":
        tags.append("recession_buy")
        warnings.append(f"当前情绪阶段为{emotion.stage_label}，逆势买入风险高")

    if plan is None:
        return BuyPlanCheckResult(
            on_plan=True,
            plan_id=None,
            plan_trade_date=None,
            violation_tags=tuple(tags),
            warnings=tuple(warnings),
        )

    on_plan = _symbol_on_plan(plan, symbol, exchange)
    if not on_plan:
        tags.append("off_plan")
        warnings.append(f"不在 {plan.trade_date} 交易计划观察名单内")

    return BuyPlanCheckResult(
        on_plan=on_plan,
        plan_id=plan.id,
        plan_trade_date=plan.trade_date,
        violation_tags=tuple(dict.fromkeys(tags)),
        warnings=tuple(warnings),
    )
