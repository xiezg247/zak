"""K 线本地读写（日 K + 1 分 K）。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from vnpy.trader.constant import Exchange, Interval
from vnpy.trader.database import get_database
from vnpy.trader.object import BarData
from vnpy_sqlite.sqlite_database import DbBarOverview

from vnpy_ashare.minute_periods import (
    bar_interval,
    is_daily_scope,
    normalize_period,
    storage_interval,
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


def get_scope_overview(
    symbol: str,
    exchange: Exchange,
    scope: str,
) -> PeriodBarOverview | None:
    if is_daily_scope(scope):
        interval_value = Interval.DAILY.value
        period = "daily"
    else:
        period = normalize_period(scope)
        interval_value = storage_interval(period)

    row = DbBarOverview.get_or_none(
        DbBarOverview.symbol == symbol,
        DbBarOverview.exchange == exchange.value,
        DbBarOverview.interval == interval_value,
    )
    if row is None or row.start is None or row.end is None or row.count <= 0:
        return None
    return PeriodBarOverview(
        symbol=symbol,
        exchange=exchange,
        period=period,
        start=row.start,
        end=row.end,
        count=row.count,
    )


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
    """读取 K 线概览。"""
    if is_daily_scope(scope):
        interval_value = Interval.DAILY.value
        period = "daily"
    else:
        period = normalize_period(scope)
        interval_value = storage_interval(period)

    query = DbBarOverview.select().where(DbBarOverview.interval == interval_value)
    rows: list[PeriodBarOverview] = []
    for row in query:
        if row.start is None or row.end is None or row.count <= 0:
            continue
        rows.append(
            PeriodBarOverview(
                symbol=row.symbol,
                exchange=Exchange(row.exchange),
                period=period,
                start=row.start,
                end=row.end,
                count=row.count,
            )
        )
    rows.sort(key=lambda item: (item.symbol, item.exchange.value))
    return rows
