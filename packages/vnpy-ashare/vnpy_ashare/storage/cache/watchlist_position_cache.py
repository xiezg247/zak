"""持仓策略短缓存（Redis 默认 + 进程 L1）。"""

from __future__ import annotations

import time
from collections.abc import Callable

from vnpy_ashare.domain.trading.signal_snapshot import SignalSnapshot
from vnpy_ashare.storage.cache.position_cache_factory import create_position_cache_backend
from vnpy_ashare.storage.cache.signal_cache_config import l1_cache_ttl_seconds
from vnpy_ashare.storage.cache.signal_payload import snapshot_from_payload, snapshot_to_payload


class _L1PositionCacheWrapper:
    def __init__(self, inner, *, ttl_sec: float) -> None:
        self._inner = inner
        self._ttl = ttl_sec
        self._load_many_hits: dict[tuple, tuple[float, dict[str, SignalSnapshot]]] = {}

    def _fresh(self, cached_at: float) -> bool:
        return time.monotonic() - cached_at <= self._ttl

    def get(self, vt_symbol: str, config_key: str, bar_as_of: str, position_key: str) -> SignalSnapshot | None:
        return self._inner.get(vt_symbol, config_key, bar_as_of, position_key)

    def get_latest(self, vt_symbol: str, config_key: str, position_key: str) -> SignalSnapshot | None:
        return self._inner.get_latest(vt_symbol, config_key, position_key)

    def load_many(
        self,
        vt_symbols: list[str],
        *,
        config_key: str,
        position_key_for: Callable[[str], str | None],
        bar_as_of_for: Callable[[str], str | None],
    ) -> dict[str, SignalSnapshot]:
        normalized = tuple(
            sorted(
                (
                    str(vt or "").strip(),
                    str(position_key_for(str(vt or "").strip()) or ""),
                    str(bar_as_of_for(str(vt or "").strip()) or ""),
                )
                for vt in vt_symbols
                if str(vt or "").strip()
            )
        )
        cache_key = (config_key, normalized)
        hit = self._load_many_hits.get(cache_key)
        if hit is not None and self._fresh(hit[0]):
            return dict(hit[1])
        loaded = self._inner.load_many(
            vt_symbols,
            config_key=config_key,
            position_key_for=position_key_for,
            bar_as_of_for=bar_as_of_for,
        )
        self._load_many_hits[cache_key] = (time.monotonic(), dict(loaded))
        return loaded

    def put(
        self,
        snapshot: SignalSnapshot,
        *,
        config_key: str,
        bar_as_of: str,
        position_key: str,
    ) -> None:
        self._load_many_hits.clear()
        self._inner.put(snapshot, config_key=config_key, bar_as_of=bar_as_of, position_key=position_key)

    def put_many(
        self,
        snapshots: dict[str, SignalSnapshot],
        *,
        config_key: str,
        position_key_for: Callable[[str], str | None],
        bar_as_of_for: Callable[[str], str | None],
    ) -> None:
        self._load_many_hits.clear()
        self._inner.put_many(
            snapshots,
            config_key=config_key,
            position_key_for=position_key_for,
            bar_as_of_for=bar_as_of_for,
        )

    def clear(self) -> None:
        self._load_many_hits.clear()
        self._inner.clear()


class WatchlistPositionDiskCache:
    """持仓区策略信号缓存；backend 与信号共用 ZAK_SIGNAL_CACHE_BACKEND。"""

    def __init__(self, backend=None, *, l1_ttl_sec: float | None = None) -> None:
        inner = backend or create_position_cache_backend()
        ttl = l1_cache_ttl_seconds() if l1_ttl_sec is None else l1_ttl_sec
        self._backend = inner if ttl <= 0 else _L1PositionCacheWrapper(inner, ttl_sec=ttl)

    def get(
        self,
        vt_symbol: str,
        config_key: str,
        bar_as_of: str,
        position_key: str,
    ) -> SignalSnapshot | None:
        return self._backend.get(vt_symbol, config_key, bar_as_of, position_key)

    def get_latest(self, vt_symbol: str, config_key: str, position_key: str) -> SignalSnapshot | None:
        return self._backend.get_latest(vt_symbol, config_key, position_key)

    def load_many(
        self,
        vt_symbols: list[str],
        *,
        config_key: str,
        position_key_for: Callable[[str], str | None],
        bar_as_of_for: Callable[[str], str | None],
    ) -> dict[str, SignalSnapshot]:
        return self._backend.load_many(
            vt_symbols,
            config_key=config_key,
            position_key_for=position_key_for,
            bar_as_of_for=bar_as_of_for,
        )

    def put(
        self,
        snapshot: SignalSnapshot,
        *,
        config_key: str,
        bar_as_of: str,
        position_key: str,
    ) -> None:
        self._backend.put(
            snapshot,
            config_key=config_key,
            bar_as_of=bar_as_of,
            position_key=position_key,
        )

    def put_many(
        self,
        snapshots: dict[str, SignalSnapshot],
        *,
        config_key: str,
        position_key_for: Callable[[str], str | None],
        bar_as_of_for: Callable[[str], str | None],
    ) -> None:
        self._backend.put_many(
            snapshots,
            config_key=config_key,
            position_key_for=position_key_for,
            bar_as_of_for=bar_as_of_for,
        )

    def clear(self) -> None:
        self._backend.clear()
