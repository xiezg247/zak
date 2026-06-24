"""计划外持仓扫描。"""

from __future__ import annotations

from vnpy.trader.constant import Exchange

from vnpy_ashare.domain.trading.plan import TradingPlanRecord
from vnpy_ashare.storage.repositories.positions import load_position_rows
from vnpy_ashare.storage.repositories.trading_plans import load_active_trading_plan
from vnpy_ashare.trading.risk.realized_pnl import today_trade_date

__all__ = ["list_off_plan_position_vt_symbols"]


def _symbol_on_plan(plan: TradingPlanRecord, symbol: str, exchange: Exchange) -> bool:
    key = (symbol, exchange.name)
    return any((item.symbol, item.exchange) == key for item in plan.symbols)


def list_off_plan_position_vt_symbols(*, trade_date: str | None = None) -> tuple[str, ...]:
    """相对当日 active 计划，不在观察名单内的持仓。"""
    day = (trade_date or today_trade_date())[:10]
    plan = load_active_trading_plan(day)
    if plan is None:
        return ()

    off_plan: list[str] = []
    for row in load_position_rows():
        symbol = str(row.get("symbol") or "")
        exchange_name = str(row.get("exchange") or "")
        if not symbol or not exchange_name:
            continue
        try:
            exchange = Exchange(exchange_name)
        except ValueError:
            continue
        if not _symbol_on_plan(plan, symbol, exchange):
            off_plan.append(f"{symbol}.{exchange.name}")
    return tuple(off_plan)
