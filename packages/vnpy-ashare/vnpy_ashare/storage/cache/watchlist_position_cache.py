"""持仓策略磁盘短缓存（键：vt_symbol + config_key + bar_as_of + position_key）。"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from vnpy_ashare.domain.trading.signal_snapshot import SignalSnapshot
from vnpy_ashare.storage.cache.db_session import cache_db_session
from vnpy_ashare.storage.cache.watchlist_signal_cache import snapshot_from_payload, snapshot_to_payload

_SCHEMA = """
CREATE TABLE IF NOT EXISTS watchlist_position_cache (
    vt_symbol TEXT NOT NULL,
    config_key TEXT NOT NULL,
    bar_as_of TEXT NOT NULL,
    position_key TEXT NOT NULL,
    payload TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (vt_symbol, config_key, bar_as_of, position_key)
);
"""


def _connect():
    return cache_db_session(_SCHEMA)


class WatchlistPositionDiskCache:
    """持仓区策略信号磁盘缓存（浮盈仍由行情实时计算）。"""

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
        with _connect() as conn:
            row = conn.execute(
                """
                SELECT payload FROM watchlist_position_cache
                WHERE vt_symbol = ? AND config_key = ? AND bar_as_of = ? AND position_key = ?
                """,
                (symbol, key, as_of, pos_key),
            ).fetchone()
        if row is None:
            return None
        try:
            return snapshot_from_payload(str(row["payload"]))
        except (TypeError, ValueError):
            return None

    def get_latest(
        self,
        vt_symbol: str,
        config_key: str,
        position_key: str,
    ) -> SignalSnapshot | None:
        symbol = str(vt_symbol or "").strip()
        key = str(config_key or "").strip()
        pos_key = str(position_key or "").strip()
        if not symbol or not key or not pos_key:
            return None
        with _connect() as conn:
            row = conn.execute(
                """
                SELECT payload FROM watchlist_position_cache
                WHERE vt_symbol = ? AND config_key = ? AND position_key = ?
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                (symbol, key, pos_key),
            ).fetchone()
        if row is None:
            return None
        try:
            return snapshot_from_payload(str(row["payload"]))
        except (TypeError, ValueError):
            return None

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

        symbols = [symbol for symbol, _, _ in targets]
        placeholders = ", ".join("?" for _ in symbols)
        with _connect() as conn:
            rows = conn.execute(
                f"""
                SELECT vt_symbol, bar_as_of, position_key, payload, updated_at
                FROM watchlist_position_cache
                WHERE config_key = ? AND vt_symbol IN ({placeholders})
                """,
                (key, *symbols),
            ).fetchall()

        by_vt: dict[str, list[dict[str, str]]] = {}
        for row in rows:
            vt = str(row["vt_symbol"] or "").strip()
            if vt:
                by_vt.setdefault(vt, []).append(
                    {
                        "bar_as_of": str(row["bar_as_of"] or ""),
                        "position_key": str(row["position_key"] or ""),
                        "payload": str(row["payload"] or ""),
                        "updated_at": str(row["updated_at"] or ""),
                    }
                )

        loaded: dict[str, SignalSnapshot] = {}
        for symbol, pos_key, bar_as_of in targets:
            candidates = [row for row in by_vt.get(symbol, []) if row["position_key"] == pos_key]
            chosen = next((row for row in candidates if row["bar_as_of"] == bar_as_of), None)
            if chosen is None and candidates:
                chosen = max(candidates, key=lambda row: row["updated_at"])
            if chosen is None:
                continue
            try:
                loaded[symbol] = snapshot_from_payload(chosen["payload"])
            except (TypeError, ValueError):
                continue
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
        payload = snapshot_to_payload(snapshot)
        updated_at = datetime.now().isoformat(timespec="seconds")
        with _connect() as conn:
            conn.execute(
                """
                INSERT INTO watchlist_position_cache(
                    vt_symbol, config_key, bar_as_of, position_key, payload, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(vt_symbol, config_key, bar_as_of, position_key) DO UPDATE SET
                    payload = excluded.payload,
                    updated_at = excluded.updated_at
                """,
                (symbol, key, as_of, pos_key, payload, updated_at),
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
        with _connect() as conn:
            conn.execute("DELETE FROM watchlist_position_cache")
