"""上午必卖提醒（极致短线：优先上午完成卖出，弱势下午不格局）。"""

from __future__ import annotations

from datetime import datetime, time
from typing import TYPE_CHECKING

from vnpy_ashare.domain.time.market_hours import (
    AFTERNOON_CLOSE,
    AFTERNOON_OPEN,
    CHINA_TZ,
    MORNING_CLOSE,
    is_ashare_trading_session,
)
from vnpy_ashare.domain.time.calendar import is_trading_day

if TYPE_CHECKING:
    from vnpy_ashare.domain.market.quote_snapshot import QuoteSnapshot
    from vnpy_ashare.domain.trading.position import PositionSnapshot

MORNING_SELL_REMIND_START = time(11, 0)


def _to_china(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=CHINA_TZ)
    return dt.astimezone(CHINA_TZ)


def is_morning_sell_reminder_window(dt: datetime | None = None) -> bool:
    """尾段上午（11:00–11:30）或下午连续竞价时段。"""
    now = _to_china(dt or datetime.now(CHINA_TZ))
    if not is_trading_day(now.date()) or not is_ashare_trading_session(now):
        return False
    clock = now.time()
    if MORNING_SELL_REMIND_START <= clock <= MORNING_CLOSE:
        return True
    if AFTERNOON_OPEN <= clock <= AFTERNOON_CLOSE:
        return True
    return False


def should_tag_morning_must_sell(
    *,
    snap: PositionSnapshot | None,
    quote: QuoteSnapshot | None,
    now: datetime | None = None,
) -> bool:
    """是否打上「上午必卖」异动（与 exit_signal=sell / 开盘止损 分工，避免重复）。"""
    if snap is None or snap.t1_locked:
        return False
    if not is_morning_sell_reminder_window(now):
        return False
    if snap.exit_signal == "sell":
        return False

    rules = snap.exit_rules or ()
    has_rule_hint = any(item.status in ("triggered", "near") for item in rules)

    now_cn = _to_china(now or datetime.now(CHINA_TZ))
    afternoon = AFTERNOON_OPEN <= now_cn.time() <= AFTERNOON_CLOSE

    if afternoon:
        if has_rule_hint:
            return True
        if quote is not None and quote.last_price > 0:
            if float(quote.change_pct or 0) <= 0:
                return True
            if quote.open_price > 0 and quote.last_price < quote.open_price:
                return True
        if snap.unrealized_pnl_pct is not None and float(snap.unrealized_pnl_pct) <= 0:
            return True
        return False

    return has_rule_hint
