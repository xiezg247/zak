"""K 线本地读写（日 K + 1 分 K）。"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime

from vnpy.trader.constant import Exchange, Interval
from vnpy.trader.database import BarOverview, get_database
from vnpy.trader.object import BarData

from vnpy_ashare.data.minute_periods import (
    MINUTE_PERIOD,
    bar_interval,
    is_daily_scope,
    normalize_period,
)

_overview_cache_lock = threading.Lock()
_overview_by_interval: dict[Interval, dict[tuple[str, Exchange], PeriodBarOverview]] | None = None


@dataclass(frozen=True)
class PeriodBarOverview:
    symbol: str
    exchange: Exchange
    period: str
    start: datetime
    end: datetime
    count: int


def get_period_overview(
    symbol: str,
    exchange: Exchange,
    period: str,
) -> PeriodBarOverview | None:
    return get_scope_overview(symbol, exchange, period)


def _interval_for_scope(scope: str) -> tuple[str, Interval]:
    if is_daily_scope(scope):
        return "daily", Interval.DAILY
    period = normalize_period(scope)
    return period, bar_interval(period)


def _overview_row_valid(row: BarOverview) -> bool:
    return row.exchange is not None and row.start is not None and row.end is not None and row.count > 0


def _row_to_overview(row: BarOverview, period: str) -> PeriodBarOverview:
    assert row.exchange is not None
    assert row.start is not None
    assert row.end is not None
    return PeriodBarOverview(
        symbol=row.symbol,
        exchange=row.exchange,
        period=period,
        start=row.start,
        end=row.end,
        count=row.count,
    )


def _period_for_interval(interval: Interval) -> str:
    if interval == Interval.DAILY:
        return "daily"
    return MINUTE_PERIOD


def invalidate_bar_overview_cache() -> None:
    """K 线写入/删除后清 overview 内存索引。"""
    global _overview_by_interval
    with _overview_cache_lock:
        _overview_by_interval = None


def _ensure_overview_cache() -> dict[Interval, dict[tuple[str, Exchange], PeriodBarOverview]]:
    global _overview_by_interval
    with _overview_cache_lock:
        if _overview_by_interval is not None:
            return _overview_by_interval

        cache: dict[Interval, dict[tuple[str, Exchange], PeriodBarOverview]] = {}
        for row in get_database().get_bar_overview():
            if not _overview_row_valid(row):
                continue
            if row.interval is None or row.exchange is None:
                continue
            period = _period_for_interval(row.interval)
            bucket = cache.setdefault(row.interval, {})
            bucket[(row.symbol, row.exchange)] = _row_to_overview(row, period)
        _overview_by_interval = cache
        return cache


def get_scope_overview(
    symbol: str,
    exchange: Exchange,
    scope: str,
) -> PeriodBarOverview | None:
    _, interval = _interval_for_scope(scope)
    cache = _ensure_overview_cache()
    return cache.get(interval, {}).get((symbol, exchange))


def load_scope_bars(
    symbol: str,
    exchange: Exchange,
    scope: str,
    start: datetime,
    end: datetime,
) -> list[BarData]:
    if is_daily_scope(scope):
        database = get_database()
        return database.load_bar_data(
            symbol,
            exchange,
            Interval.DAILY,
            start,
            end,
        )
    return load_period_bars(symbol, exchange, scope, start, end)


def load_period_bars(
    symbol: str,
    exchange: Exchange,
    period: str,
    start: datetime,
    end: datetime,
) -> list[BarData]:
    normalize_period(period)
    database = get_database()
    return database.load_bar_data(
        symbol,
        exchange,
        bar_interval(period),
        start,
        end,
    )


def iter_bar_overviews(*, scope: str) -> list[PeriodBarOverview]:
    """读取 K 线概览（跟随 vt_setting 中的 database.name）。"""
    _, interval = _interval_for_scope(scope)
    rows = list(_ensure_overview_cache().get(interval, {}).values())
    rows.sort(key=lambda item: (item.symbol, item.exchange.value))
    return rows


def delete_scope_bars(symbol: str, exchange: Exchange, scope: str) -> bool:
    """删除指定 scope 下的本地 K 线；无数据时返回 False。"""
    if get_scope_overview(symbol, exchange, scope) is None:
        return False
    _, interval = _interval_for_scope(scope)
    get_database().delete_bar_data(symbol, exchange, interval)
    invalidate_bar_overview_cache()
    return True
