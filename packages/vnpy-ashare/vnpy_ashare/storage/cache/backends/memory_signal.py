"""内存信号 cache（单测 / 无 Redis 环境）。"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from vnpy_ashare.domain.symbols.stock import canonical_vt_symbol
from vnpy_ashare.domain.trading.signal_snapshot import SignalSnapshot
from vnpy_ashare.storage.cache.signal_payload import snapshot_from_payload, snapshot_to_payload


@dataclass
class _Entry:
    payload: str
    updated_at: str


class MemorySignalCacheBackend:
    def __init__(self) -> None:
        self._rows: dict[tuple[str, str, str], _Entry] = {}

    def get(self, vt_symbol: str, config_key: str, bar_as_of: str) -> SignalSnapshot | None:
        vt = canonical_vt_symbol(str(vt_symbol or "").strip()) or str(vt_symbol or "").strip()
        key = str(config_key or "").strip()
        as_of = str(bar_as_of or "")
        entry = self._rows.get((vt, key, as_of))
        if entry is None:
            return None
        return snapshot_from_payload(entry.payload)

    def get_latest(self, vt_symbol: str, config_key: str) -> SignalSnapshot | None:
        vt = canonical_vt_symbol(str(vt_symbol or "").strip()) or str(vt_symbol or "").strip()
        key = str(config_key or "").strip()
        candidates = [entry for (sym, cfg, _), entry in self._rows.items() if sym == vt and cfg == key]
        if not candidates:
            return None
        latest = max(candidates, key=lambda item: item.updated_at)
        return snapshot_from_payload(latest.payload)

    def load_many(
        self,
        vt_symbols: list[str],
        *,
        config_key: str,
        bar_as_of_for: Callable[[str], str | None],
    ) -> dict[str, SignalSnapshot]:
        loaded: dict[str, SignalSnapshot] = {}
        for vt in vt_symbols:
            canon = canonical_vt_symbol(str(vt or "").strip()) or str(vt or "").strip()
            if not canon:
                continue
            as_of = str(bar_as_of_for(canon) or "")
            snap = self.get(canon, config_key, as_of) if as_of else None
            if snap is None:
                snap = self.get_latest(canon, config_key)
            if snap is not None:
                loaded[canon] = snap
        return loaded

    def put(self, snapshot: SignalSnapshot, *, config_key: str, bar_as_of: str) -> None:
        symbol = canonical_vt_symbol(str(snapshot.vt_symbol or "").strip()) or str(snapshot.vt_symbol or "").strip()
        key = str(config_key or "").strip()
        as_of = str(bar_as_of or "")
        if not symbol or not key:
            return
        self._rows[(symbol, key, as_of)] = _Entry(
            payload=snapshot_to_payload(snapshot),
            updated_at=datetime.now().isoformat(timespec="seconds"),
        )

    def put_many(
        self,
        snapshots: dict[str, SignalSnapshot],
        *,
        config_key: str,
        bar_as_of_for: Callable[[str], str | None],
    ) -> None:
        for vt_symbol, snapshot in snapshots.items():
            bar_as_of = bar_as_of_for(vt_symbol) or snapshot.as_of or ""
            self.put(snapshot, config_key=config_key, bar_as_of=bar_as_of)

    def clear(self) -> None:
        self._rows.clear()
