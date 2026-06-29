"""进程内 L1 包装：短 TTL 避免 UI 刷新重复打 Redis/PG。"""

from __future__ import annotations

import time
from collections.abc import Callable

from vnpy_ashare.domain.trading.signal_snapshot import SignalSnapshot
from vnpy_ashare.storage.cache.backends import SignalCacheBackend


class L1SignalCacheWrapper:
    def __init__(self, inner: SignalCacheBackend, *, ttl_sec: float) -> None:
        self._inner = inner
        self._ttl = ttl_sec
        self._get_hits: dict[tuple[str, str, str], tuple[float, SignalSnapshot]] = {}
        self._latest_hits: dict[tuple[str, str], tuple[float, SignalSnapshot | None]] = {}
        self._load_many_hits: dict[tuple, tuple[float, dict[str, SignalSnapshot]]] = {}

    def _fresh(self, cached_at: float) -> bool:
        return time.monotonic() - cached_at <= self._ttl

    def _invalidate_all(self) -> None:
        self._get_hits.clear()
        self._latest_hits.clear()
        self._load_many_hits.clear()

    def get(self, vt_symbol: str, config_key: str, bar_as_of: str) -> SignalSnapshot | None:
        key = (config_key, vt_symbol, bar_as_of)
        hit = self._get_hits.get(key)
        if hit is not None and self._fresh(hit[0]):
            return hit[1]
        value = self._inner.get(vt_symbol, config_key, bar_as_of)
        if value is not None:
            self._get_hits[key] = (time.monotonic(), value)
        return value

    def get_latest(self, vt_symbol: str, config_key: str) -> SignalSnapshot | None:
        key = (config_key, vt_symbol)
        hit = self._latest_hits.get(key)
        if hit is not None and self._fresh(hit[0]):
            return hit[1]
        value = self._inner.get_latest(vt_symbol, config_key)
        self._latest_hits[key] = (time.monotonic(), value)
        return value

    def load_many(
        self,
        vt_symbols: list[str],
        *,
        config_key: str,
        bar_as_of_for: Callable[[str], str | None],
    ) -> dict[str, SignalSnapshot]:
        normalized = tuple(
            sorted(
                (
                    vt,
                    str(bar_as_of_for(vt) or ""),
                )
                for vt in vt_symbols
                if str(vt or "").strip()
            )
        )
        cache_key = (config_key, normalized)
        hit = self._load_many_hits.get(cache_key)
        if hit is not None and self._fresh(hit[0]):
            return dict(hit[1])
        loaded = self._inner.load_many(vt_symbols, config_key=config_key, bar_as_of_for=bar_as_of_for)
        self._load_many_hits[cache_key] = (time.monotonic(), dict(loaded))
        for vt, snapshot in loaded.items():
            as_of = str(bar_as_of_for(vt) or snapshot.as_of or "")
            self._get_hits[(config_key, vt, as_of)] = (time.monotonic(), snapshot)
        return loaded

    def put(self, snapshot: SignalSnapshot, *, config_key: str, bar_as_of: str) -> None:
        self._invalidate_all()
        self._inner.put(snapshot, config_key=config_key, bar_as_of=bar_as_of)

    def put_many(
        self,
        snapshots: dict[str, SignalSnapshot],
        *,
        config_key: str,
        bar_as_of_for: Callable[[str], str | None],
    ) -> None:
        self._invalidate_all()
        self._inner.put_many(snapshots, config_key=config_key, bar_as_of_for=bar_as_of_for)

    def clear(self) -> None:
        self._invalidate_all()
        self._inner.clear()
