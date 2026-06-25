"""信号 cache backend 工厂。"""

from __future__ import annotations

from typing import Protocol

from vnpy_ashare.domain.trading.signal_snapshot import SignalSnapshot
from vnpy_ashare.storage.cache.signal_cache_config import resolve_signal_cache_backend


class SignalCacheBackend(Protocol):
    def get(self, vt_symbol: str, config_key: str, bar_as_of: str) -> SignalSnapshot | None: ...

    def get_latest(self, vt_symbol: str, config_key: str) -> SignalSnapshot | None: ...

    def load_many(
        self,
        vt_symbols: list[str],
        *,
        config_key: str,
        bar_as_of_for,
    ) -> dict[str, SignalSnapshot]: ...

    def put(self, snapshot: SignalSnapshot, *, config_key: str, bar_as_of: str) -> None: ...

    def put_many(
        self,
        snapshots: dict[str, SignalSnapshot],
        *,
        config_key: str,
        bar_as_of_for,
    ) -> None: ...

    def clear(self) -> None: ...


def create_signal_cache_backend() -> SignalCacheBackend:
    backend = resolve_signal_cache_backend()
    if backend == "pg":
        from vnpy_ashare.storage.cache.backends.pg_signal import PgSignalCacheBackend

        return PgSignalCacheBackend()
    if backend == "memory":
        from vnpy_ashare.storage.cache.backends.memory_signal import MemorySignalCacheBackend

        return MemorySignalCacheBackend()
    from vnpy_ashare.storage.cache.backends.redis_signal import RedisSignalCacheBackend

    return RedisSignalCacheBackend()
