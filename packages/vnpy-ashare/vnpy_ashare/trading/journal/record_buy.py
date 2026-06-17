"""登记持仓 → 买入流水。"""

from __future__ import annotations

from typing import Any

from vnpy.trader.constant import Exchange

from vnpy_ashare.quotes.market.emotion_cycle import load_emotion_cycle_snapshot
from vnpy_ashare.storage.repositories.trade_journal import insert_trade_journal_entry
from vnpy_ashare.trading.journal.plan_check import check_buy_against_plan
from vnpy_ashare.trading.journal.violation_notify import publish_journal_violation


def record_buy_from_position(
    symbol: str,
    exchange: Exchange,
    *,
    cost_price: float,
    volume: int,
    buy_date: str,
    reason: str = "",
    notify_engine: Any | None = None,
) -> int | None:
    check = check_buy_against_plan(symbol, exchange, trade_date=buy_date)
    emotion = load_emotion_cycle_snapshot(fetch_if_missing=True)
    entry_id = insert_trade_journal_entry(
        symbol=symbol,
        exchange=exchange.name,
        side="buy",
        trade_date=buy_date,
        price=cost_price,
        volume=volume,
        plan_id=check.plan_id,
        on_plan=check.on_plan,
        violation_tags=check.violation_tags,
        reason=reason,
        emotion_stage=emotion.stage if emotion is not None else "",
    )
    if entry_id is not None and check.violation_tags and notify_engine is not None:
        publish_journal_violation(
            notify_engine,
            symbol=symbol,
            exchange=exchange.name,
            side="buy",
            violation_tags=check.violation_tags,
            reason=reason,
            emotion_stage=emotion.stage if emotion is not None else "",
        )
    return entry_id
