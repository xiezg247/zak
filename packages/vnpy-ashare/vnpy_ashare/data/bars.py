"""K 线下载与自选池读取。"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from vnpy.trader.constant import Exchange, Interval
from vnpy.trader.database import get_database
from vnpy.trader.datafeed import get_datafeed
from vnpy.trader.object import HistoryRequest

from vnpy_ashare.storage.app_db import import_watchlist_csv, load_universe_rows, load_watchlist_rows
from vnpy_ashare.data.bar_store import iter_bar_overviews
from vnpy_ashare.config import is_ashare_exchange
from vnpy_ashare.data.minute_periods import (
    DEFAULT_MINUTE_DOWNLOAD_MONTHS,
    bar_interval,
    normalize_period,
)
from vnpy_ashare.domain.models import StockItem
from vnpy_ashare.data.tickflow_klines import fetch_history_bars


def load_watchlist(path: Path | None = None, ashare_only: bool = True) -> list[StockItem]:
    """从 SQLite 读取自选池；若指定 path 则从 CSV 导入后返回。"""
    if path is not None:
        import_watchlist_csv(path)

    items: list[StockItem] = []
    for symbol, exchange, name in load_watchlist_rows():
        if ashare_only and not is_ashare_exchange(exchange):
            raise ValueError(f"自选池含非 A 股交易所 {exchange.value}（{symbol}），本项目仅支持 SSE/SZSE/BJ")
        items.append(StockItem(symbol=symbol, exchange=exchange, name=name))
    return items


def download_bars(
    symbol: str,
    exchange: Exchange,
    interval: Interval,
    start: datetime,
    end: datetime,
    output=print,
    ashare_only: bool = True,
) -> int:
    """下载 K 线并写入本地数据库，返回保存条数。"""
    if ashare_only and not is_ashare_exchange(exchange):
        raise ValueError(f"非 A 股交易所: {exchange.value}")

    req = HistoryRequest(
        symbol=symbol,
        exchange=exchange,
        interval=interval,
        start=start,
        end=end,
    )

    datafeed = get_datafeed()
    if not datafeed.init(output):
        raise RuntimeError("数据服务初始化失败，请检查 .env 中的 API Key / Token，并在设置页「从 .env 同步」")

    bars = datafeed.query_bar_history(req, output=output)
    if not bars:
        raise RuntimeError(f"未获取到数据: {symbol}.{exchange.value}")

    database = get_database()
    database.save_bar_data(bars)
    return len(bars)


def default_minute_download_start(end: datetime | None = None) -> datetime:
    anchor = end or datetime.now()
    return anchor - timedelta(days=DEFAULT_MINUTE_DOWNLOAD_MONTHS * 30)


def download_period_bars(
    symbol: str,
    exchange: Exchange,
    period: str,
    start: datetime,
    end: datetime,
    output=print,
    ashare_only: bool = True,
) -> int:
    """下载指定周期分 K 并写入本地，返回保存条数。"""
    if ashare_only and not is_ashare_exchange(exchange):
        raise ValueError(f"非 A 股交易所: {exchange.value}")

    period = normalize_period(period)
    item = StockItem(symbol=symbol, exchange=exchange)
    bars = fetch_history_bars(item, period=period, start=start, end=end)
    if not bars:
        raise RuntimeError(f"未获取到 {period} 数据: {symbol}.{exchange.value}")

    database = get_database()
    for bar in bars:
        bar.interval = bar_interval(period)
    database.save_bar_data(bars)
    return len(bars)


def cleanup_invalid_daily_bars() -> list[tuple[str, Exchange]]:
    """删除缺少起止时间或条数为 0 的日 K 概览及数据。"""
    database = get_database()
    removed: list[tuple[str, Exchange]] = []
    for row in database.get_bar_overview():
        if row.interval != Interval.DAILY:
            continue
        if row.exchange is None:
            continue
        invalid = row.start is None or row.end is None or row.count <= 0 or row.start > row.end
        if not invalid:
            continue
        database.delete_bar_data(row.symbol, row.exchange, Interval.DAILY)
        removed.append((row.symbol, row.exchange))
    return removed


def load_downloaded_stocks(*, scope: str = "daily") -> list[StockItem]:
    """读取本地已下载 K 线列表，并尽量补全证券名称。"""
    name_map = {(symbol, exchange): name for symbol, exchange, name in load_universe_rows()}
    items: list[StockItem] = []
    for row in iter_bar_overviews(scope=scope):
        name = name_map.get((row.symbol, row.exchange), "")
        items.append(StockItem(symbol=row.symbol, exchange=row.exchange, name=name))
    return items
