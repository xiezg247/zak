"""A 股交易日历（Tushare Pro 本地缓存，失败时降级为跳过周末）。"""

from __future__ import annotations

from datetime import date, timedelta

from vnpy_ashare.storage.repositories.trade_calendar import (
    ensure_calendar_covers,
    load_open_trading_days,
    lookup_trading_day,
)


def _fallback_is_trading_day(day: date) -> bool:
    return day.weekday() < 5


def is_trading_day(day: date) -> bool:
    cached = lookup_trading_day(day)
    if cached is not None:
        return cached

    ensure_calendar_covers(day)
    cached = lookup_trading_day(day)
    if cached is not None:
        return cached
    return _fallback_is_trading_day(day)


def last_trading_day(*, on_or_before: date | None = None) -> date:
    """返回 on_or_before（默认今天）及之前的最近 A 股交易日。"""
    current = on_or_before or date.today()
    ensure_calendar_covers(current)
    while not is_trading_day(current):
        current -= timedelta(days=1)
    return current


def trading_days_between(start: date, end: date) -> list[date]:
    """返回区间内 A 股交易日列表（bulk 读 trade_calendar 表）。"""
    return load_open_trading_days(start, end)
