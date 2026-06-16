"""K 线下载与自选池读取。

数据源分工（A 股）::

    实时行情 / 盘中快照 / Redis 全市场   → TickFlow
    历史日 K / 历史分 K（落本地库）       → Tushare Pro

读本地已下载 K 线一律走 ``bar_store`` / ``load_scope_bars``，与上述来源无关。
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from vnpy.trader.constant import Exchange, Interval
from vnpy.trader.database import get_database

from vnpy_ashare.config import is_ashare_exchange
from vnpy_ashare.data.bar_store import invalidate_bar_overview_cache, iter_bar_overviews
from vnpy_ashare.data.minute_periods import (
    DEFAULT_MINUTE_DOWNLOAD_MONTHS,
    normalize_period,
)
from vnpy_ashare.domain.symbols import StockItem
from vnpy_ashare.storage.repositories.universe import load_universe_names_for_keys
from vnpy_ashare.storage.repositories.watchlist import import_watchlist_csv, load_watchlist_rows


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
    """下载 K 线并写入本地数据库，返回保存条数（历史 K 线走 Tushare Pro）。"""
    if ashare_only and not is_ashare_exchange(exchange):
        raise ValueError(f"非 A 股交易所: {exchange.value}")

    if interval == Interval.DAILY:
        from vnpy_ashare.integrations.tushare.bars import download_daily_bars_tushare

        return download_daily_bars_tushare(symbol, exchange, start=start, end=end)

    if interval == Interval.MINUTE:
        from vnpy_ashare.integrations.tushare.bars import download_minute_bars_tushare

        return download_minute_bars_tushare(symbol, exchange, start=start, end=end, period="1m")

    raise RuntimeError(f"历史 K 线下载仅支持日 K 与 1 分 K（Tushare），当前 interval={interval.value}")


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
    """下载指定周期分 K 并写入本地，返回保存条数（历史分 K 走 Tushare stk_mins）。"""
    if ashare_only and not is_ashare_exchange(exchange):
        raise ValueError(f"非 A 股交易所: {exchange.value}")

    period = normalize_period(period)
    from vnpy_ashare.integrations.tushare.bars import download_minute_bars_tushare

    return download_minute_bars_tushare(
        symbol,
        exchange,
        start=start,
        end=end,
        period=period,
    )


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
    if removed:
        invalidate_bar_overview_cache()
    return removed


def load_downloaded_stocks(*, scope: str = "daily") -> list[StockItem]:
    """读取本地已下载 K 线列表，并尽量补全证券名称。"""
    return load_downloaded_stocks_page(scope=scope, offset=0, limit=None)


def count_downloaded_stocks(*, scope: str = "daily") -> int:
    """本地已下载标的总数。"""
    return len(iter_bar_overviews(scope=scope))


def load_downloaded_stocks_page(
    *,
    scope: str = "daily",
    offset: int = 0,
    limit: int | None = 50,
) -> list[StockItem]:
    """分页读取本地已下载 K 线列表；limit 为 None 时返回全部。"""
    rows = iter_bar_overviews(scope=scope)
    if limit is None:
        page_rows = rows[offset:]
    else:
        page_rows = rows[offset : offset + max(limit, 0)]
    return _overview_rows_to_items(page_rows)


def _overview_rows_to_items(rows) -> list[StockItem]:
    name_map = load_universe_names_for_keys([(row.symbol, row.exchange) for row in rows])
    items: list[StockItem] = []
    for row in rows:
        name = name_map.get((row.symbol, row.exchange), "")
        items.append(StockItem(symbol=row.symbol, exchange=row.exchange, name=name))
    return items


def search_downloaded_stocks_page(
    *,
    scope: str = "daily",
    keyword: str,
    offset: int = 0,
    limit: int = 50,
) -> tuple[list[StockItem], int]:
    """在本地已下载列表中按代码/名称搜索并分页。"""
    keyword = keyword.strip().lower()
    if not keyword:
        total = count_downloaded_stocks(scope=scope)
        items = load_downloaded_stocks_page(scope=scope, offset=offset, limit=limit)
        return items, total

    rows = iter_bar_overviews(scope=scope)
    name_map = load_universe_names_for_keys([(row.symbol, row.exchange) for row in rows])
    matched: list[StockItem] = []
    for row in rows:
        name = name_map.get((row.symbol, row.exchange), "")
        item = StockItem(symbol=row.symbol, exchange=row.exchange, name=name)
        if keyword in item.search_key:
            matched.append(item)
    total = len(matched)
    page_size = max(limit, 0)
    return matched[offset : offset + page_size], total
