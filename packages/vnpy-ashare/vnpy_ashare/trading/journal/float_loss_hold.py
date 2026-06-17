"""浮亏扛单检测与流水打标。"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from vnpy_ashare.config.preferences.trading_risk import load_trading_risk_prefs
from vnpy_ashare.domain.trading.position import PositionSnapshot
from vnpy_ashare.storage.repositories.trade_journal import (
    has_sell_journal_since,
    has_violation_tag_on_date,
    insert_trade_journal_entry,
)
from vnpy_ashare.trading.journal.violation_notify import publish_journal_violation
from vnpy_ashare.trading.risk.realized_pnl import today_trade_date


def float_loss_threshold_pct() -> float:
    prefs = load_trading_risk_prefs()
    return float(prefs.caution_float_pct)


def is_float_loss_hold(
    snap: PositionSnapshot,
    *,
    threshold_pct: float | None = None,
) -> bool:
    if snap.unrealized_pnl_pct is None:
        return False
    threshold = threshold_pct if threshold_pct is not None else float_loss_threshold_pct()
    if float(snap.unrealized_pnl_pct) > threshold:
        return False
    symbol, exchange = snap.vt_symbol.split(".", 1)
    since = (snap.buy_date or "")[:10]
    if not since:
        since = today_trade_date()
    if has_sell_journal_since(symbol, exchange, since_date=since):
        return False
    return True


def scan_float_loss_holds(
    position_cache: Mapping[str, PositionSnapshot] | None,
) -> list[str]:
    if not position_cache:
        return []
    return [vt for vt, snap in position_cache.items() if is_float_loss_hold(snap)]


def record_float_loss_hold_if_needed(
    snap: PositionSnapshot,
    *,
    trade_date: str | None = None,
    notify_engine: Any | None = None,
) -> int | None:
    if not is_float_loss_hold(snap):
        return None
    day = (trade_date or today_trade_date())[:10]
    symbol, exchange = snap.vt_symbol.split(".", 1)
    if has_violation_tag_on_date(symbol, exchange, trade_date=day, tag="float_loss_hold"):
        return None
    price = snap.last_price if snap.last_price is not None and snap.last_price > 0 else snap.cost_price
    entry_id = insert_trade_journal_entry(
        symbol=symbol,
        exchange=exchange,
        side="hold",
        trade_date=day,
        price=price,
        volume=snap.volume,
        on_plan=True,
        violation_tags=("float_loss_hold",),
        pnl=snap.unrealized_pnl,
        pnl_pct=snap.unrealized_pnl_pct,
        reason="浮亏扛单（无卖出流水）",
        emotion_stage="",
    )
    if entry_id is not None and notify_engine is not None:

        publish_journal_violation(
            notify_engine,
            symbol=symbol,
            exchange=exchange,
            side="hold",
            violation_tags=("float_loss_hold",),
            reason="浮亏扛单（无卖出流水）",
            vt_symbol=snap.vt_symbol,
        )
    return entry_id


def scan_and_record_float_loss_holds(
    position_cache: Mapping[str, PositionSnapshot] | None,
    *,
    notify_engine: Any | None = None,
) -> int:
    recorded = 0
    for vt_symbol in scan_float_loss_holds(position_cache):
        snap = position_cache.get(vt_symbol) if position_cache else None
        if snap is None:
            continue
        if record_float_loss_hold_if_needed(snap, notify_engine=notify_engine) is not None:
            recorded += 1
    return recorded
