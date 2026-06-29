"""全市场行情快照进程级 Hub（统一 Redis 读结果与 UI / 选股缓存）。"""

from __future__ import annotations

import threading

from vnpy_ashare.domain.screener.quotes_snapshot import MarketQuotesSnapshot
from vnpy_ashare.quotes.core.quote_l1_cache import seq_matches
from vnpy_ashare.quotes.core.quote_rows import set_market_quote_rows_cache
from vnpy_ashare.quotes.core.redis_store import get_redis_quote_store

_lock = threading.Lock()
_process_snapshot: MarketQuotesSnapshot | None = None


def get_process_quote_snapshot() -> MarketQuotesSnapshot | None:
    with _lock:
        snapshot = _process_snapshot
    if snapshot is None:
        return None
    if not seq_matches(get_redis_quote_store().get_quote_seq()):
        clear_process_quote_snapshot()
        return None
    return snapshot


def clear_process_quote_snapshot() -> None:
    global _process_snapshot
    with _lock:
        _process_snapshot = None


def publish_market_snapshot(snapshot: MarketQuotesSnapshot) -> None:
    """写入进程级快照并同步市场页行缓存。"""
    global _process_snapshot
    with _lock:
        _process_snapshot = snapshot
    set_market_quote_rows_cache(snapshot.rows)
