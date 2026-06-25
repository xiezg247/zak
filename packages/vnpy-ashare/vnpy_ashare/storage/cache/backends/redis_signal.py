"""Redis 自选信号 cache（盘中默认 backend）。"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime
from typing import Any

from vnpy_ashare.domain.symbols.stock import canonical_vt_symbol
from vnpy_ashare.domain.trading.signal_snapshot import SignalSnapshot
from vnpy_ashare.quotes.core.redis_store import KEY_PREFIX, create_redis_client
from vnpy_ashare.storage.cache.signal_cache_config import signal_cache_ttl_seconds
from vnpy_ashare.storage.cache.signal_payload import snapshot_from_payload, snapshot_to_payload


def _signal_key(config_key: str, bar_as_of: str, vt_symbol: str) -> str:
    return f"{KEY_PREFIX}:cache:signal:{config_key}:{bar_as_of}:{vt_symbol}"


def _latest_key(config_key: str, vt_symbol: str) -> str:
    return f"{KEY_PREFIX}:cache:signal:latest:{config_key}:{vt_symbol}"


def _envelope(payload: str, *, bar_as_of: str, updated_at: str) -> str:
    return json.dumps(
        {"payload": payload, "bar_as_of": bar_as_of, "updated_at": updated_at},
        ensure_ascii=False,
    )


def _parse_envelope(text: str) -> dict[str, str] | None:
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    payload = str(data.get("payload") or "")
    if not payload:
        return None
    return {
        "payload": payload,
        "bar_as_of": str(data.get("bar_as_of") or ""),
        "updated_at": str(data.get("updated_at") or ""),
    }


class RedisSignalCacheBackend:
    def __init__(self, client=None) -> None:
        self._client = client or create_redis_client()
        self._ttl = signal_cache_ttl_seconds()

    def _decode_snapshot(self, raw: str | None) -> SignalSnapshot | None:
        if not raw:
            return None
        envelope = _parse_envelope(raw)
        if envelope is None:
            try:
                return snapshot_from_payload(raw)
            except (json.JSONDecodeError, TypeError, ValueError):
                return None
        try:
            return snapshot_from_payload(envelope["payload"])
        except (json.JSONDecodeError, TypeError, ValueError):
            return None

    def get(self, vt_symbol: str, config_key: str, bar_as_of: str) -> SignalSnapshot | None:
        vt = canonical_vt_symbol(str(vt_symbol or "").strip()) or str(vt_symbol or "").strip()
        key = str(config_key or "").strip()
        as_of = str(bar_as_of or "")
        if not vt or not key or not as_of:
            return None
        raw = self._client.get(_signal_key(key, as_of, vt))
        return self._decode_snapshot(raw)

    def get_latest(self, vt_symbol: str, config_key: str) -> SignalSnapshot | None:
        vt = canonical_vt_symbol(str(vt_symbol or "").strip()) or str(vt_symbol or "").strip()
        key = str(config_key or "").strip()
        if not vt or not key:
            return None
        raw = self._client.get(_latest_key(key, vt))
        return self._decode_snapshot(raw)

    def load_many(
        self,
        vt_symbols: list[str],
        *,
        config_key: str,
        bar_as_of_for: Callable[[str], str | None],
    ) -> dict[str, SignalSnapshot]:
        key = str(config_key or "").strip()
        if not key:
            return {}

        normalized: list[str] = []
        seen: set[str] = set()
        for vt in vt_symbols:
            canon = canonical_vt_symbol(str(vt or "").strip()) or str(vt or "").strip()
            if not canon or canon in seen:
                continue
            seen.add(canon)
            normalized.append(canon)
        if not normalized:
            return {}

        exact_keys = [_signal_key(key, str(bar_as_of_for(vt) or ""), vt) for vt in normalized]
        pipe = self._client.pipeline(transaction=False)
        for redis_key in exact_keys:
            pipe.get(redis_key)
        exact_values = pipe.execute()

        loaded: dict[str, SignalSnapshot] = {}
        missing: list[str] = []
        for vt, raw in zip(normalized, exact_values, strict=True):
            snap = self._decode_snapshot(raw)
            if snap is not None:
                loaded[vt] = snap
            else:
                missing.append(vt)

        if missing:
            pipe = self._client.pipeline(transaction=False)
            for vt in missing:
                pipe.get(_latest_key(key, vt))
            latest_values = pipe.execute()
            for vt, raw in zip(missing, latest_values, strict=True):
                snap = self._decode_snapshot(raw)
                if snap is not None:
                    loaded[vt] = snap
        return loaded

    def put(self, snapshot: SignalSnapshot, *, config_key: str, bar_as_of: str) -> None:
        symbol = canonical_vt_symbol(str(snapshot.vt_symbol or "").strip()) or str(snapshot.vt_symbol or "").strip()
        key = str(config_key or "").strip()
        as_of = str(bar_as_of or "")
        if not symbol or not key:
            return
        payload = snapshot_to_payload(snapshot)
        updated_at = datetime.now().isoformat(timespec="seconds")
        blob = _envelope(payload, bar_as_of=as_of, updated_at=updated_at)
        pipe = self._client.pipeline(transaction=False)
        pipe.set(_signal_key(key, as_of, symbol), blob, ex=self._ttl)
        pipe.set(_latest_key(key, symbol), blob, ex=self._ttl)
        pipe.execute()

    def put_many(
        self,
        snapshots: dict[str, SignalSnapshot],
        *,
        config_key: str,
        bar_as_of_for: Callable[[str], str | None],
    ) -> None:
        if not snapshots:
            return
        pipe = self._client.pipeline(transaction=False)
        updated_at = datetime.now().isoformat(timespec="seconds")
        for vt_symbol, snapshot in snapshots.items():
            symbol = canonical_vt_symbol(str(snapshot.vt_symbol or vt_symbol or "").strip()) or str(vt_symbol or "").strip()
            key = str(config_key or "").strip()
            as_of = str(bar_as_of_for(vt_symbol) or snapshot.as_of or "")
            if not symbol or not key:
                continue
            blob = _envelope(snapshot_to_payload(snapshot), bar_as_of=as_of, updated_at=updated_at)
            pipe.set(_signal_key(key, as_of, symbol), blob, ex=self._ttl)
            pipe.set(_latest_key(key, symbol), blob, ex=self._ttl)
        pipe.execute()

    def clear(self) -> None:
        pattern = f"{KEY_PREFIX}:cache:signal:*"
        cursor = 0
        while True:
            cursor, keys = self._client.scan(cursor=cursor, match=pattern, count=200)
            if keys:
                self._client.delete(*keys)
            if cursor == 0:
                break
