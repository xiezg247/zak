"""自选信号磁盘短缓存（键：vt_symbol + config_key + bar_as_of）。"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from vnpy_ashare.domain.signal_snapshot import SignalSnapshot
from vnpy_common.paths import get_app_db_path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS watchlist_signal_cache (
    vt_symbol TEXT NOT NULL,
    config_key TEXT NOT NULL,
    bar_as_of TEXT NOT NULL,
    payload TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (vt_symbol, config_key, bar_as_of)
);
"""


def _cache_db_path() -> Path:
    return get_app_db_path().parent / "watchlist_signal_cache.db"


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


def snapshot_to_payload(snapshot: SignalSnapshot) -> str:
    return json.dumps(
        {
            "vt_symbol": snapshot.vt_symbol,
            "strategy_id": snapshot.strategy_id,
            "as_of": snapshot.as_of,
            "signal": snapshot.signal,
            "signal_label": snapshot.signal_label,
            "signal_date": snapshot.signal_date,
            "ref_buy_price": snapshot.ref_buy_price,
            "ref_sell_price": snapshot.ref_sell_price,
            "strength": snapshot.strength,
            "reason_summary": snapshot.reason_summary,
            "reasons": list(snapshot.reasons),
            "warnings": list(snapshot.warnings),
        },
        ensure_ascii=False,
    )


def snapshot_from_payload(text: str) -> SignalSnapshot:
    data: dict[str, Any] = json.loads(text)
    return SignalSnapshot(
        vt_symbol=str(data.get("vt_symbol") or ""),
        strategy_id=str(data.get("strategy_id") or ""),
        as_of=str(data.get("as_of") or ""),
        signal=data.get("signal") or "na",
        signal_label=str(data.get("signal_label") or "—"),
        signal_date=data.get("signal_date"),
        ref_buy_price=data.get("ref_buy_price"),
        ref_sell_price=data.get("ref_sell_price"),
        strength=data.get("strength"),
        reason_summary=str(data.get("reason_summary") or ""),
        reasons=tuple(data.get("reasons") or ()),
        warnings=tuple(data.get("warnings") or ()),
    )


class WatchlistSignalDiskCache:
    """自选信号 Worker 专用磁盘缓存。"""

    def get(self, vt_symbol: str, config_key: str, bar_as_of: str) -> SignalSnapshot | None:
        symbol = str(vt_symbol or "").strip()
        key = str(config_key or "").strip()
        as_of = str(bar_as_of or "")
        if not symbol or not key:
            return None
        with _connect() as conn:
            row = conn.execute(
                """
                SELECT payload FROM watchlist_signal_cache
                WHERE vt_symbol = ? AND config_key = ? AND bar_as_of = ?
                """,
                (symbol, key, as_of),
            ).fetchone()
        if row is None:
            return None
        try:
            return snapshot_from_payload(str(row["payload"]))
        except (json.JSONDecodeError, TypeError, ValueError):
            return None

    def get_latest(self, vt_symbol: str, config_key: str) -> SignalSnapshot | None:
        """取该标的最近一条缓存（冷启动 bar_as_of 未就绪时的回退）。"""
        symbol = str(vt_symbol or "").strip()
        key = str(config_key or "").strip()
        if not symbol or not key:
            return None
        with _connect() as conn:
            row = conn.execute(
                """
                SELECT payload FROM watchlist_signal_cache
                WHERE vt_symbol = ? AND config_key = ?
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                (symbol, key),
            ).fetchone()
        if row is None:
            return None
        try:
            return snapshot_from_payload(str(row["payload"]))
        except (json.JSONDecodeError, TypeError, ValueError):
            return None

    def load_many(
        self,
        vt_symbols: list[str],
        *,
        config_key: str,
        bar_as_of_for: Callable[[str], str | None],
    ) -> dict[str, SignalSnapshot]:
        loaded: dict[str, SignalSnapshot] = {}
        for vt in vt_symbols:
            bar_as_of = bar_as_of_for(vt) or ""
            snap = self.get(vt, config_key, bar_as_of)
            if snap is None:
                snap = self.get_latest(vt, config_key)
            if snap is not None:
                loaded[vt] = snap
        return loaded

    def put(
        self,
        snapshot: SignalSnapshot,
        *,
        config_key: str,
        bar_as_of: str,
    ) -> None:
        symbol = str(snapshot.vt_symbol or "").strip()
        key = str(config_key or "").strip()
        as_of = str(bar_as_of or "")
        if not symbol or not key:
            return
        payload = snapshot_to_payload(snapshot)
        updated_at = datetime.now().isoformat(timespec="seconds")
        with _connect() as conn:
            conn.execute(
                """
                INSERT INTO watchlist_signal_cache(
                    vt_symbol, config_key, bar_as_of, payload, updated_at
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(vt_symbol, config_key, bar_as_of) DO UPDATE SET
                    payload = excluded.payload,
                    updated_at = excluded.updated_at
                """,
                (symbol, key, as_of, payload, updated_at),
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
        with _connect() as conn:
            conn.execute("DELETE FROM watchlist_signal_cache")
