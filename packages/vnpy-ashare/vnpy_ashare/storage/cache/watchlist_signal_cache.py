"""自选信号磁盘短缓存（键：vt_symbol + config_key + bar_as_of）。"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime
from typing import Any

from vnpy_ashare.domain.symbols.stock import canonical_vt_symbol
from vnpy_ashare.domain.trading.signal_snapshot import SignalSnapshot, signal_snapshot_to_dict
from vnpy_ashare.storage.cache.db_session import cache_db_session

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


def _connect():
    return cache_db_session(_SCHEMA)


def snapshot_to_payload(snapshot: SignalSnapshot) -> str:
    data = signal_snapshot_to_dict(snapshot)
    data["reasons"] = list(snapshot.reasons)
    data["warnings"] = list(snapshot.warnings)
    return json.dumps(data, ensure_ascii=False)


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
        last_close=data.get("last_close"),
        action_ref_buy_price=data.get("action_ref_buy_price"),
        action_ref_sell_price=data.get("action_ref_sell_price"),
        fast_ma=data.get("fast_ma"),
        slow_ma=data.get("slow_ma"),
        volume_ratio_5d=data.get("volume_ratio_5d"),
        ma_gap_pct=data.get("ma_gap_pct"),
        strength_cross=data.get("strength_cross"),
        strength_alignment=data.get("strength_alignment"),
        strength_volume=data.get("strength_volume"),
        strength_pattern=data.get("strength_pattern"),
        relative_index_pct=data.get("relative_index_pct"),
    )


class WatchlistSignalDiskCache:
    """自选信号 Worker 专用磁盘缓存。"""

    def get(self, vt_symbol: str, config_key: str, bar_as_of: str) -> SignalSnapshot | None:
        vt = canonical_vt_symbol(str(vt_symbol or "").strip()) or str(vt_symbol or "").strip()
        key = str(config_key or "").strip()
        as_of = str(bar_as_of or "")
        if not vt or not key or not as_of:
            return None
        with _connect() as conn:
            row = conn.execute(
                """
                SELECT payload FROM watchlist_signal_cache
                WHERE vt_symbol = ? AND config_key = ? AND bar_as_of = ?
                """,
                (vt, key, as_of),
            ).fetchone()
        if row is None:
            return None
        try:
            return snapshot_from_payload(str(row["payload"]))
        except (json.JSONDecodeError, TypeError, ValueError):
            return None

    def get_latest(self, vt_symbol: str, config_key: str) -> SignalSnapshot | None:
        """取该标的最近一条缓存（冷启动 bar_as_of 未就绪时的回退）。"""
        vt = canonical_vt_symbol(str(vt_symbol or "").strip()) or str(vt_symbol or "").strip()
        key = str(config_key or "").strip()
        if not vt or not key:
            return None
        with _connect() as conn:
            row = conn.execute(
                """
                SELECT payload FROM watchlist_signal_cache
                WHERE vt_symbol = ? AND config_key = ?
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                (vt, key),
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

        placeholders = ", ".join("?" for _ in normalized)
        with _connect() as conn:
            rows = conn.execute(
                f"""
                SELECT vt_symbol, bar_as_of, payload, updated_at
                FROM watchlist_signal_cache
                WHERE config_key = ? AND vt_symbol IN ({placeholders})
                """,
                (key, *normalized),
            ).fetchall()

        by_vt: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            vt = str(row["vt_symbol"] or "").strip()
            if vt:
                by_vt.setdefault(vt, []).append(dict(row))

        loaded: dict[str, SignalSnapshot] = {}
        for vt in normalized:
            bar_as_of = bar_as_of_for(vt) or ""
            candidates = by_vt.get(vt, [])
            chosen = next((row for row in candidates if str(row.get("bar_as_of") or "") == bar_as_of), None)
            if chosen is None and candidates:
                chosen = max(candidates, key=lambda row: str(row.get("updated_at") or ""))
            if chosen is None:
                continue
            try:
                loaded[vt] = snapshot_from_payload(str(chosen["payload"]))
            except (json.JSONDecodeError, TypeError, ValueError):
                continue
        return loaded

    def put(
        self,
        snapshot: SignalSnapshot,
        *,
        config_key: str,
        bar_as_of: str,
    ) -> None:
        symbol = canonical_vt_symbol(str(snapshot.vt_symbol or "").strip()) or str(snapshot.vt_symbol or "").strip()
        key = str(config_key or "").strip()
        as_of = str(bar_as_of or "")
        if not symbol or not key:
            return
        payload = snapshot_to_payload(snapshot)
        updated_at = datetime.now().isoformat(timespec="seconds")
        with _connect() as conn:
            conn.execute(
                """
                INSERT INTO watchlist_signal_cache (
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
