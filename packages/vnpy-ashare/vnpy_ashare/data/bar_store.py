"""K 线本地读写（日 K + 1 分 K）。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from vnpy.trader.constant import Exchange, Interval
from vnpy.trader.database import BarOverview, get_database
from vnpy.trader.object import BarData

from vnpy_ashare.data.minute_periods import (
    bar_interval,
    is_daily_scope,
    normalize_period,
)


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
    return (
        row.exchange is not None
        and row.start is not None
        and row.end is not None
        and row.count > 0
    )


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


def get_scope_overview(
    symbol: str,
    exchange: Exchange,
    scope: str,
) -> PeriodBarOverview | None:
    period, interval = _interval_for_scope(scope)
    for row in get_database().get_bar_overview():
        if row.symbol != symbol or row.exchange != exchange or row.interval != interval:
            continue
        if not _overview_row_valid(row):
            return None
        return _row_to_overview(row, period)
    return None


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
    period, interval = _interval_for_scope(scope)
    rows: list[PeriodBarOverview] = []
    for row in get_database().get_bar_overview():
        if row.interval != interval or not _overview_row_valid(row):
            continue
        rows.append(_row_to_overview(row, period))
    rows.sort(key=lambda item: (item.symbol, item.exchange.value))
    return rows


def delete_scope_bars(symbol: str, exchange: Exchange, scope: str) -> bool:
    """删除指定 scope 下的本地 K 线；无数据时返回 False。"""
    if get_scope_overview(symbol, exchange, scope) is None:
        return False
    _, interval = _interval_for_scope(scope)
    get_database().delete_bar_data(symbol, exchange, interval)
    return True
