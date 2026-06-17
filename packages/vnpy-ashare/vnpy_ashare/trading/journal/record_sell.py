"""移出持仓 → 卖出流水。"""

from __future__ import annotations

from datetime import datetime

from vnpy.trader.constant import Exchange

from vnpy_ashare.domain.time.market_hours import CHINA_TZ
from vnpy_ashare.domain.trading.position import compute_unrealized_pnl
from vnpy_ashare.quotes.market.emotion_cycle import load_emotion_cycle_snapshot
from vnpy_ashare.storage.repositories.trade_journal import insert_trade_journal_entry, query_latest_buy_journal


def record_sell_from_position(
    symbol: str,
    exchange: Exchange,
    *,
    cost_price: float,
    volume: int,
    sell_price: float,
    sell_date: str | None = None,
    reason: str = "",
) -> int | None:
    if sell_price <= 0 or volume <= 0 or cost_price <= 0:
        return None
    trade_date = (sell_date or datetime.now(CHINA_TZ).date().isoformat())[:10]
    _, pnl, pnl_pct = compute_unrealized_pnl(cost_price, volume, sell_price)
    latest_buy = query_latest_buy_journal(symbol, exchange.name)
    emotion = load_emotion_cycle_snapshot(fetch_if_missing=True)
    return insert_trade_journal_entry(
        symbol=symbol,
        exchange=exchange.name,
        side="sell",
        trade_date=trade_date,
        price=sell_price,
        volume=volume,
        plan_id=latest_buy.plan_id if latest_buy is not None else None,
        on_plan=latest_buy.on_plan if latest_buy is not None else True,
        violation_tags=(),
        pnl=pnl,
        pnl_pct=pnl_pct,
        reason=reason,
        emotion_stage=emotion.stage if emotion is not None else "",
    )
