"""加仓违规检测与增量买入流水。"""

from __future__ import annotations

from typing import Any

from vnpy.trader.constant import Exchange

from vnpy_ashare.domain.position_snapshot import PositionRecord
from vnpy_ashare.quotes.market.emotion_cycle import load_emotion_cycle_snapshot
from vnpy_ashare.storage.repositories.trade_journal import insert_trade_journal_entry
from vnpy_ashare.trading.journal.plan_check import check_buy_against_plan
from vnpy_ashare.trading.journal.violation_notify import publish_journal_violation


def should_tag_add_loss(
    record: PositionRecord,
    *,
    new_volume: int,
    last_price: float | None,
) -> bool:
    if new_volume <= record.volume:
        return False
    if last_price is None or last_price <= 0:
        return False
    return last_price < record.cost_price


def record_volume_increase_buy(
    symbol: str,
    exchange: Exchange,
    *,
    cost_price: float,
    delta_volume: int,
    buy_date: str,
    add_loss: bool,
    notify_engine: Any | None = None,
) -> int | None:
    if delta_volume <= 0:
        return None
    extra_tags = ("add_loss",) if add_loss else ()

    check = check_buy_against_plan(symbol, exchange, trade_date=buy_date)
    tags = tuple(dict.fromkeys((*check.violation_tags, *extra_tags)))
    emotion = load_emotion_cycle_snapshot(fetch_if_missing=True)
    entry_id = insert_trade_journal_entry(
        symbol=symbol,
        exchange=exchange.name,
        side="buy",
        trade_date=buy_date,
        price=cost_price,
        volume=delta_volume,
        plan_id=check.plan_id,
        on_plan=check.on_plan,
        violation_tags=tags,
        reason="加仓登记",
        emotion_stage=emotion.stage if emotion is not None else "",
    )
    if entry_id is not None and tags and notify_engine is not None:
        publish_journal_violation(
            notify_engine,
            symbol=symbol,
            exchange=exchange.name,
            side="buy",
            violation_tags=tags,
            reason="加仓登记",
            emotion_stage=emotion.stage if emotion is not None else "",
        )
    return entry_id
