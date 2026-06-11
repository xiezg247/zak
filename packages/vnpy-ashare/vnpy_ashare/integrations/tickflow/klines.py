"""TickFlow K 线拉取并转为 VeighNa BarData。"""

from __future__ import annotations

from datetime import datetime

import pandas as pd
from vnpy.trader.constant import Exchange, Interval
from vnpy.trader.object import BarData

from vnpy_ashare.data.minute_periods import bar_interval, normalize_period
from vnpy_ashare.domain.models import StockItem
from vnpy_tickflow.client import get_tickflow_client
from vnpy_tickflow.klines import fetch_klines_paged
from vnpy_tickflow.mapping import CHINA_TZ

PERIOD_TO_INTERVAL: dict[str, Interval] = {
    "1m": Interval.MINUTE,
    "1d": Interval.DAILY,
}


def _parse_bar_datetime(row: pd.Series) -> datetime:
    trade_time = row.get("trade_time")
    if isinstance(trade_time, str) and trade_time.strip():
        dt = datetime.strptime(trade_time.strip(), "%Y-%m-%d %H:%M:%S")
        return dt.replace(tzinfo=CHINA_TZ)
    timestamp = int(row.get("timestamp", 0) or 0)
    return datetime.fromtimestamp(timestamp / 1000, tz=CHINA_TZ)


def dataframe_to_bars(
    df: pd.DataFrame,
    *,
    symbol: str,
    exchange: Exchange,
    interval: Interval,
    gateway_name: str = "TICKFLOW",
) -> list[BarData]:
    if df is None or df.empty:
        return []

    bars: list[BarData] = []
    for _, row in df.iterrows():
        bars.append(
            BarData(
                symbol=symbol,
                exchange=exchange,
                datetime=_parse_bar_datetime(row),
                interval=interval,
                open_price=float(row.get("open", 0) or 0),
                high_price=float(row.get("high", 0) or 0),
                low_price=float(row.get("low", 0) or 0),
                close_price=float(row.get("close", 0) or 0),
                volume=float(row.get("volume", 0) or 0),
                turnover=float(row.get("amount", 0) or 0),
                gateway_name=gateway_name,
            )
        )
    return bars


def fetch_intraday_bars(item: StockItem, *, period: str = "1m") -> list[BarData]:
    client = get_tickflow_client()
    df = client.klines.intraday(item.tickflow_symbol, period=period, as_dataframe=True)
    return dataframe_to_bars(
        df,
        symbol=item.symbol,
        exchange=item.exchange,
        interval=Interval.MINUTE,
    )


def fetch_minute_bars(item: StockItem, *, period: str = "1m", count: int = 240) -> list[BarData]:
    client = get_tickflow_client()
    df = client.klines.get(
        item.tickflow_symbol,
        period=period,
        count=count,
        as_dataframe=True,
    )
    interval = PERIOD_TO_INTERVAL.get(period, Interval.MINUTE)
    return dataframe_to_bars(
        df,
        symbol=item.symbol,
        exchange=item.exchange,
        interval=interval,
    )


def fetch_history_bars(
    item: StockItem,
    *,
    period: str,
    start: datetime,
    end: datetime,
) -> list[BarData]:
    """按时间区间分页拉取历史分 K（需 TickFlow Pro）。"""
    period = normalize_period(period)
    start_ms = int(start.replace(tzinfo=CHINA_TZ).timestamp() * 1000)
    end_ms = int(end.replace(tzinfo=CHINA_TZ).timestamp() * 1000)
    client = get_tickflow_client()
    df = fetch_klines_paged(client, item.tickflow_symbol, period, start_ms, end_ms)
    return dataframe_to_bars(
        df,
        symbol=item.symbol,
        exchange=item.exchange,
        interval=bar_interval(period),
    )
