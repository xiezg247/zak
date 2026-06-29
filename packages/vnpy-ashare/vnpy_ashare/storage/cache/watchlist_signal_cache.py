"""自选信号短缓存（Redis 默认 + 进程 L1）。"""

from __future__ import annotations

from collections.abc import Callable

from vnpy_ashare.domain.trading.signal_snapshot import SignalSnapshot
from vnpy_ashare.storage.cache.backends import SignalCacheBackend, create_signal_cache_backend
from vnpy_ashare.storage.cache.l1_signal_cache import L1SignalCacheWrapper
from vnpy_ashare.storage.cache.signal_cache_config import l1_cache_ttl_seconds
from vnpy_ashare.storage.cache.signal_payload import snapshot_from_payload, snapshot_to_payload

__all__ = (
    "WatchlistSignalDiskCache",
    "snapshot_from_payload",
    "snapshot_to_payload",
)


class WatchlistSignalDiskCache:
    """自选信号 Worker / UI 缓存；backend 由 ZAK_SIGNAL_CACHE_BACKEND 控制。"""

    def __init__(self, backend: SignalCacheBackend | None = None, *, l1_ttl_sec: float | None = None) -> None:
        inner = backend or create_signal_cache_backend()
        ttl = l1_cache_ttl_seconds() if l1_ttl_sec is None else l1_ttl_sec
        self._backend = inner if ttl <= 0 else L1SignalCacheWrapper(inner, ttl_sec=ttl)

    def get(self, vt_symbol: str, config_key: str, bar_as_of: str) -> SignalSnapshot | None:
        return self._backend.get(vt_symbol, config_key, bar_as_of)

    def get_latest(self, vt_symbol: str, config_key: str) -> SignalSnapshot | None:
        return self._backend.get_latest(vt_symbol, config_key)

    def load_many(
        self,
        vt_symbols: list[str],
        *,
        config_key: str,
        bar_as_of_for: Callable[[str], str | None],
    ) -> dict[str, SignalSnapshot]:
        return self._backend.load_many(vt_symbols, config_key=config_key, bar_as_of_for=bar_as_of_for)

    def put(self, snapshot: SignalSnapshot, *, config_key: str, bar_as_of: str) -> None:
        self._backend.put(snapshot, config_key=config_key, bar_as_of=bar_as_of)

    def put_many(
        self,
        snapshots: dict[str, SignalSnapshot],
        *,
        config_key: str,
        bar_as_of_for: Callable[[str], str | None],
    ) -> None:
        self._backend.put_many(snapshots, config_key=config_key, bar_as_of_for=bar_as_of_for)

    def clear(self) -> None:
        self._backend.clear()
