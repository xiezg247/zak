"""内存持仓 cache backend。"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from vnpy_ashare.domain.trading.signal_snapshot import SignalSnapshot
from vnpy_ashare.storage.cache.signal_payload import snapshot_from_payload, snapshot_to_payload


@dataclass
class _Entry:
    payload: str
    updated_at: str


class MemoryPositionCacheBackend:
    def __init__(self) -> None:
        self._rows: dict[tuple[str, str, str, str], _Entry] = {}

    def get(
        self,
        vt_symbol: str,
        config_key: str,
        bar_as_of: str,
        position_key: str,
    ) -> SignalSnapshot | None:
        entry = self._rows.get(
            (
                str(vt_symbol or "").strip(),
                str(config_key or "").strip(),
                str(bar_as_of or ""),
                str(position_key or "").strip(),
            )
        )
        if entry is None:
            return None
        return snapshot_from_payload(entry.payload)

    def get_latest(self, vt_symbol: str, config_key: str, position_key: str) -> SignalSnapshot | None:
        symbol = str(vt_symbol or "").strip()
        key = str(config_key or "").strip()
        pos_key = str(position_key or "").strip()
        candidates = [
            entry
            for (sym, cfg, _, pk), entry in self._rows.items()
            if sym == symbol and cfg == key and pk == pos_key
        ]
        if not candidates:
            return None
        latest = max(candidates, key=lambda item: item.updated_at)
        return snapshot_from_payload(latest.payload)

    def load_many(
        self,
        vt_symbols: list[str],
        *,
        config_key: str,
        position_key_for: Callable[[str], str | None],
        bar_as_of_for: Callable[[str], str | None],
    ) -> dict[str, SignalSnapshot]:
        loaded: dict[str, SignalSnapshot] = {}
        for vt in vt_symbols:
            symbol = str(vt or "").strip()
            pos_key = str(position_key_for(symbol) or "").strip()
            if not symbol or not pos_key:
                continue
            as_of = str(bar_as_of_for(symbol) or "")
            snap = self.get(symbol, config_key, as_of, pos_key) if as_of else None
            if snap is None:
                snap = self.get_latest(symbol, config_key, pos_key)
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
        self._rows[(symbol, key, as_of, pos_key)] = _Entry(
            payload=snapshot_to_payload(snapshot),
            updated_at=datetime.now().isoformat(timespec="seconds"),
        )

    def put_many(
        self,
        snapshots: dict[str, SignalSnapshot],
        *,
        config_key: str,
        position_key_for: Callable[[str], str | None],
        bar_as_of_for: Callable[[str], str | None],
    ) -> None:
        for vt_symbol, snapshot in snapshots.items():
            pos_key = position_key_for(vt_symbol)
            if not pos_key:
                continue
            bar_as_of = bar_as_of_for(vt_symbol) or snapshot.as_of or ""
            self.put(
                snapshot,
                config_key=config_key,
                bar_as_of=bar_as_of,
                position_key=pos_key,
            )

    def clear(self) -> None:
        self._rows.clear()
