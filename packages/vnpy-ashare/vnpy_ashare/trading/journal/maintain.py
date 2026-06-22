"""交易流水维护：编辑、删除与盈亏重算。"""

from __future__ import annotations

from vnpy_ashare.domain.trading.journal import TradeJournalEntry
from vnpy_ashare.domain.trading.position import compute_unrealized_pnl
from vnpy_ashare.storage.repositories.trade_journal import (
    delete_trade_journal_entry,
    get_trade_journal_entry,
    query_latest_buy_journal,
    update_trade_journal_entry,
)

__all__ = [
    "delete_journal_entry",
    "recalc_sell_pnl",
    "update_journal_entry",
]


def recalc_sell_pnl(
    *,
    cost_price: float,
    volume: int,
    sell_price: float,
) -> tuple[float, float]:
    _, pnl, pnl_pct = compute_unrealized_pnl(cost_price, volume, sell_price)
    return round(pnl or 0.0, 2), round(pnl_pct or 0.0, 2)


def _resolve_sell_cost(entry: TradeJournalEntry) -> float | None:
    buy = query_latest_buy_journal(entry.symbol, entry.exchange)
    if buy is None or buy.price <= 0:
        return None
    return buy.price


def update_journal_entry(
    entry_id: int,
    *,
    trade_date: str | None = None,
    price: float | None = None,
    volume: int | None = None,
    mode: str | None = None,
    on_plan: bool | None = None,
    violation_tags: tuple[str, ...] | list[str] | None = None,
    reason: str | None = None,
    pnl: float | None = None,
    pnl_pct: float | None = None,
    recalc_pnl: bool = True,
) -> TradeJournalEntry | None:
    existing = get_trade_journal_entry(entry_id)
    if existing is None:
        return None

    next_price = price if price is not None else existing.price
    next_volume = volume if volume is not None else existing.volume
    next_pnl = pnl
    next_pnl_pct = pnl_pct

    if existing.side == "sell" and recalc_pnl and pnl is None:
        cost = _resolve_sell_cost(existing)
        if cost is not None and next_price > 0 and next_volume > 0:
            next_pnl, next_pnl_pct = recalc_sell_pnl(
                cost_price=cost,
                volume=next_volume,
                sell_price=next_price,
            )

    ok = update_trade_journal_entry(
        entry_id,
        trade_date=trade_date,
        price=price,
        volume=volume,
        mode=mode,
        on_plan=on_plan,
        violation_tags=violation_tags,
        pnl=next_pnl,
        pnl_pct=next_pnl_pct,
        reason=reason,
    )
    if not ok:
        return None
    return get_trade_journal_entry(entry_id)


def delete_journal_entry(entry_id: int) -> bool:
    return delete_trade_journal_entry(entry_id)
