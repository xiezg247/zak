"""交易日遍历（领域层，无 screener / quotes 依赖）。"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date, timedelta

from vnpy_ashare.domain.time.calendar import is_trading_day, last_trading_day

DEFAULT_LOOKBACK_DAYS = 10
DEFAULT_FORWARD_DAYS = 3


def iter_trade_date_strs(
    *,
    max_lookback: int = DEFAULT_LOOKBACK_DAYS,
    start: date | None = None,
) -> Iterator[str]:
    """从 start（默认最近交易日）向前遍历交易日。"""
    current = start or last_trading_day()
    for _ in range(max(1, max_lookback)):
        yield current.strftime("%Y%m%d")
        current = last_trading_day(on_or_before=current - timedelta(days=1))


def iter_forward_trade_date_strs(
    *,
    count: int = DEFAULT_FORWARD_DAYS,
    start: date | None = None,
) -> tuple[str, ...]:
    """从 start（默认最近交易日）的下一交易日起，向后取 count 个交易日（YYYYMMDD）。"""
    horizon = max(1, int(count))
    anchor = last_trading_day(on_or_before=start or date.today())
    current = anchor + timedelta(days=1)
    dates: list[str] = []
    guard = anchor + timedelta(days=horizon * 4 + 21)
    while len(dates) < horizon and current <= guard:
        if is_trading_day(current):
            dates.append(current.strftime("%Y%m%d"))
        current += timedelta(days=1)
    return tuple(dates)
