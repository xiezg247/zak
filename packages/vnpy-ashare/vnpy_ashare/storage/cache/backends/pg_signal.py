"""PostgreSQL cache schema 信号 backend（fallback / 测试）。"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from vnpy_ashare.domain.symbols.stock import canonical_vt_symbol
from vnpy_ashare.domain.trading.signal_snapshot import SignalSnapshot
from vnpy_ashare.storage.cache.signal_payload import snapshot_from_payload, snapshot_to_payload
from vnpy_ashare.storage.repository.app import AppBaseRepository
from vnpy_common.storage.tables.cache import watchlist_signal_cache as wsc


class PgSignalCacheBackend(AppBaseRepository):
    table = wsc

    def get(self, vt_symbol: str, config_key: str, bar_as_of: str) -> SignalSnapshot | None:
        vt = canonical_vt_symbol(str(vt_symbol or "").strip()) or str(vt_symbol or "").strip()
        key = str(config_key or "").strip()
        as_of = str(bar_as_of or "")
        if not vt or not key or not as_of:
            return None
        row = self.fetchone(
            select(wsc.c.payload).where(
                wsc.c.vt_symbol == vt,
                wsc.c.config_key == key,
                wsc.c.bar_as_of == as_of,
            )
        )
        if row is None:
            return None
        try:
            return snapshot_from_payload(str(row["payload"]))
        except (json.JSONDecodeError, TypeError, ValueError):
            return None

    def get_latest(self, vt_symbol: str, config_key: str) -> SignalSnapshot | None:
        vt = canonical_vt_symbol(str(vt_symbol or "").strip()) or str(vt_symbol or "").strip()
        key = str(config_key or "").strip()
        if not vt or not key:
            return None
        row = self.fetchone(select(wsc.c.payload).where(wsc.c.vt_symbol == vt, wsc.c.config_key == key).order_by(wsc.c.updated_at.desc()).limit(1))
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

        rows = self.fetchall(
            select(wsc.c.vt_symbol, wsc.c.bar_as_of, wsc.c.payload, wsc.c.updated_at).where(
                wsc.c.config_key == key,
                wsc.c.vt_symbol.in_(normalized),
            )
        )
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

    def put(self, snapshot: SignalSnapshot, *, config_key: str, bar_as_of: str) -> None:
        symbol = canonical_vt_symbol(str(snapshot.vt_symbol or "").strip()) or str(snapshot.vt_symbol or "").strip()
        key = str(config_key or "").strip()
        as_of = str(bar_as_of or "")
        if not symbol or not key:
            return
        values = {
            "vt_symbol": symbol,
            "config_key": key,
            "bar_as_of": as_of,
            "payload": snapshot_to_payload(snapshot),
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        }

        def _write(conn) -> None:
            stmt = pg_insert(wsc).values(values)
            excluded = stmt.excluded
            conn.execute_stmt(
                stmt.on_conflict_do_update(
                    index_elements=[wsc.c.vt_symbol, wsc.c.config_key, wsc.c.bar_as_of],
                    set_={"payload": excluded.payload, "updated_at": excluded.updated_at},
                )
            )

        self.run(_write)

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
        self.delete_matching()
