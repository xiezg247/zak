"""情绪周期快照进程内 TTL 缓存（与 quote_rows / cache_invalidation 解耦）。"""

from __future__ import annotations

from typing import Any

from vnpy_ashare.quotes.core.cache_ttl import TtlCache

_CACHE_TTL_SEC = 30.0
_emotion_cache: TtlCache[Any] = TtlCache()


def peek_emotion_cycle_snapshot(*, max_age_sec: float = _CACHE_TTL_SEC) -> Any | None:
    """读取内存缓存，不触发任何 I/O。"""
    return _emotion_cache.peek(max_age_sec=max_age_sec)


def store_emotion_cycle_snapshot(snapshot: Any | None) -> None:
    """写入内存缓存（市场页 Worker / 控制器刷新后调用）。"""
    _emotion_cache.store(snapshot)


def invalidate_emotion_cycle_cache() -> None:
    """行情缓存更新时丢弃情绪快照，避免与旧广度不一致。"""
    _emotion_cache.invalidate()
