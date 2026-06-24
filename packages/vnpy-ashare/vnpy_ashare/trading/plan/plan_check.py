"""买入 vs 交易计划校验。"""

from __future__ import annotations

from vnpy.trader.constant import Exchange

from vnpy_ashare.domain.trading.plan import TradingPlanRecord
from vnpy_ashare.domain.trading.plan_check import BuyPlanCheckResult
from vnpy_ashare.quotes.market.emotion_cycle import load_emotion_cycle_snapshot
from vnpy_ashare.storage.repositories.trading_plans import load_active_trading_plan

__all__ = ["BuyPlanCheckResult", "check_buy_against_plan"]


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
