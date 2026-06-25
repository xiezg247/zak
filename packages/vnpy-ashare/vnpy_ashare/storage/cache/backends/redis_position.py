"""Redis 持仓策略 cache。"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from vnpy_ashare.domain.trading.signal_snapshot import SignalSnapshot
from vnpy_ashare.quotes.core.redis_store import KEY_PREFIX, create_redis_client
from vnpy_ashare.storage.cache.backends.redis_signal import _envelope, _parse_envelope
from vnpy_ashare.storage.cache.signal_cache_config import signal_cache_ttl_seconds
from vnpy_ashare.storage.cache.signal_payload import snapshot_from_payload, snapshot_to_payload


def _position_key(config_key: str, bar_as_of: str, vt_symbol: str, position_key: str) -> str:
    return f"{KEY_PREFIX}:cache:position:{config_key}:{bar_as_of}:{vt_symbol}:{position_key}"


def _latest_position_key(config_key: str, vt_symbol: str, position_key: str) -> str:
    return f"{KEY_PREFIX}:cache:position:latest:{config_key}:{vt_symbol}:{position_key}"


def _decode_snapshot(raw: str | None) -> SignalSnapshot | None:
    if not raw:
        return None
    envelope = _parse_envelope(raw)
    if envelope is None:
        try:
            return snapshot_from_payload(raw)
        except (TypeError, ValueError):
            return None
    try:
        return snapshot_from_payload(envelope["payload"])
    except (TypeError, ValueError):
        return None


class RedisPositionCacheBackend:
    def __init__(self, client=None) -> None:
        self._client = client or create_redis_client()
        self._ttl = signal_cache_ttl_seconds()

    def get(
        self,
        vt_symbol: str,
        config_key: str,
        bar_as_of: str,
        position_key: str,
    ) -> SignalSnapshot | None:
        symbol = str(vt_symbol or "").strip()
        key = str(config_key or "").strip()
        pos_key = str(position_key or "").strip()
        as_of = str(bar_as_of or "")
        if not symbol or not key or not pos_key:
            return None
        return _decode_snapshot(self._client.get(_position_key(key, as_of, symbol, pos_key)))

    def get_latest(self, vt_symbol: str, config_key: str, position_key: str) -> SignalSnapshot | None:
        symbol = str(vt_symbol or "").strip()
        key = str(config_key or "").strip()
        pos_key = str(position_key or "").strip()
        if not symbol or not key or not pos_key:
            return None
        return _decode_snapshot(self._client.get(_latest_position_key(key, symbol, pos_key)))

    def load_many(
        self,
        vt_symbols: list[str],
        *,
        config_key: str,
        position_key_for: Callable[[str], str | None],
        bar_as_of_for: Callable[[str], str | None],
    ) -> dict[str, SignalSnapshot]:
        key = str(config_key or "").strip()
        if not key:
            return {}

        targets: list[tuple[str, str, str]] = []
        seen: set[str] = set()
        for vt in vt_symbols:
            symbol = str(vt or "").strip()
            if not symbol or symbol in seen:
                continue
            pos_key = str(position_key_for(symbol) or "").strip()
            if not pos_key:
                continue
            seen.add(symbol)
            targets.append((symbol, pos_key, bar_as_of_for(symbol) or ""))
        if not targets:
            return {}

        pipe = self._client.pipeline(transaction=False)
        for symbol, pos_key, bar_as_of in targets:
            pipe.get(_position_key(key, bar_as_of, symbol, pos_key))
        exact_values = pipe.execute()

        loaded: dict[str, SignalSnapshot] = {}
        missing: list[tuple[str, str, str]] = []
        for target, raw in zip(targets, exact_values, strict=True):
            symbol, pos_key, bar_as_of = target
            snap = _decode_snapshot(raw)
            if snap is not None:
                loaded[symbol] = snap
            else:
                missing.append(target)

        if missing:
            pipe = self._client.pipeline(transaction=False)
            for symbol, pos_key, _ in missing:
                pipe.get(_latest_position_key(key, symbol, pos_key))
            latest_values = pipe.execute()
            for (symbol, _, _), raw in zip(missing, latest_values, strict=True):
                snap = _decode_snapshot(raw)
                if snap is not None:
                    loaded[symbol] = snap
        return loaded

    def put(
        self,
        snapshot: SignalSnapshot,
        *,
        config_key: str,
        bar_as_of: str,
        position_key: str,
    ) -> None:
        symbol = str(snapshot.vt_symbol or "").strip()
        key = str(config_key or "").strip()
        pos_key = str(position_key or "").strip()
        as_of = str(bar_as_of or "")
        if not symbol or not key or not pos_key:
            return
        updated_at = datetime.now().isoformat(timespec="seconds")
        blob = _envelope(snapshot_to_payload(snapshot), bar_as_of=as_of, updated_at=updated_at)
        pipe = self._client.pipeline(transaction=False)
        pipe.set(_position_key(key, as_of, symbol, pos_key), blob, ex=self._ttl)
        pipe.set(_latest_position_key(key, symbol, pos_key), blob, ex=self._ttl)
        pipe.execute()

    def put_many(
        self,
        snapshots: dict[str, SignalSnapshot],
        *,
        config_key: str,
        position_key_for: Callable[[str], str | None],
        bar_as_of_for: Callable[[str], str | None],
    ) -> None:
        if not snapshots:
            return
        pipe = self._client.pipeline(transaction=False)
        updated_at = datetime.now().isoformat(timespec="seconds")
        for vt_symbol, snapshot in snapshots.items():
            pos_key = str(position_key_for(vt_symbol) or "").strip()
            if not pos_key:
                continue
            symbol = str(snapshot.vt_symbol or vt_symbol or "").strip()
            key = str(config_key or "").strip()
            as_of = str(bar_as_of_for(vt_symbol) or snapshot.as_of or "")
            if not symbol or not key:
                continue
            blob = _envelope(snapshot_to_payload(snapshot), bar_as_of=as_of, updated_at=updated_at)
            pipe.set(_position_key(key, as_of, symbol, pos_key), blob, ex=self._ttl)
            pipe.set(_latest_position_key(key, symbol, pos_key), blob, ex=self._ttl)
        pipe.execute()

    def clear(self) -> None:
        pattern = f"{KEY_PREFIX}:cache:position:*"
        cursor = 0
        while True:
            cursor, keys = self._client.scan(cursor=cursor, match=pattern, count=200)
            if keys:
                self._client.delete(*keys)
            if cursor == 0:
                break
