"""市场概览快照进程内 TTL 缓存（供 UI peek、盘后只读）。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vnpy_ashare.quotes.core.cache_ttl import TtlCache

if TYPE_CHECKING:
    from vnpy_ashare.domain.market.overview import MarketOverviewData

_INTRADAY_TTL_SEC = 30.0
_OFF_SESSION_TTL_SEC = 86400.0

_overview_cache: TtlCache[MarketOverviewData] = TtlCache()


def peek_market_overview_data(*, intraday: bool) -> MarketOverviewData | None:
    """读取内存缓存，不触发任何 I/O。"""
    ttl = _INTRADAY_TTL_SEC if intraday else _OFF_SESSION_TTL_SEC
    return _overview_cache.peek(max_age_sec=ttl)


def store_market_overview_data(data: MarketOverviewData | None) -> None:
    """Worker / 控制器全量刷新后写入。"""
    _overview_cache.store(data)


def invalidate_market_overview_cache() -> None:
    _overview_cache.invalidate()
