"""持仓 cache backend 工厂。"""

from __future__ import annotations

from vnpy_ashare.storage.cache.signal_cache_config import resolve_signal_cache_backend


def create_position_cache_backend():
    backend = resolve_signal_cache_backend()
    if backend == "pg":
        from vnpy_ashare.storage.cache.backends.pg_position import PgPositionCacheBackend

        return PgPositionCacheBackend()
    if backend == "memory":
        from vnpy_ashare.storage.cache.backends.memory_position import MemoryPositionCacheBackend

        return MemoryPositionCacheBackend()
    from vnpy_ashare.storage.cache.backends.redis_position import RedisPositionCacheBackend

    return RedisPositionCacheBackend()
