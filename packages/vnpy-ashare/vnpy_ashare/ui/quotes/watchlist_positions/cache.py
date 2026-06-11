"""持仓策略磁盘短缓存（键：vt_symbol + config_key + bar_as_of + position_key）。"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from vnpy_ashare.domain.signal_snapshot import SignalSnapshot
from vnpy_ashare.ui.quotes.watchlist_signals.cache import snapshot_from_payload, snapshot_to_payload
from vnpy_common.paths import get_app_db_path

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


def _cache_db_path() -> Path:
    return get_app_db_path().parent / "watchlist_position_cache.db"


@contextmanager
def _connect():
    path = _cache_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(_SCHEMA)
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


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
        loaded: dict[str, SignalSnapshot] = {}
        for vt in vt_symbols:
            pos_key = position_key_for(vt) or ""
            if not pos_key:
                continue
            bar_as_of = bar_as_of_for(vt) or ""
            snap = self.get(vt, config_key, bar_as_of, pos_key)
            if snap is None:
                snap = self.get_latest(vt, config_key, pos_key)
            if snap is not None:
                loaded[vt] = snap
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
