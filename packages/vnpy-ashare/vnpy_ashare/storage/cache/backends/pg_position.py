"""PostgreSQL 持仓策略 cache backend。"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from vnpy_ashare.domain.trading.signal_snapshot import SignalSnapshot
from vnpy_ashare.storage.repository.app import AppBaseRepository
from vnpy_ashare.storage.cache.signal_payload import snapshot_from_payload, snapshot_to_payload
from vnpy_common.storage.tables.cache import watchlist_position_cache as wpc


class PgPositionCacheBackend(AppBaseRepository):
    table = wpc

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
        row = self.fetchone(
            select(wpc.c.payload).where(
                wpc.c.vt_symbol == symbol,
                wpc.c.config_key == key,
                wpc.c.bar_as_of == as_of,
                wpc.c.position_key == pos_key,
            )
        )
        if row is None:
            return None
        try:
            return snapshot_from_payload(str(row["payload"]))
        except (TypeError, ValueError):
            return None

    def get_latest(self, vt_symbol: str, config_key: str, position_key: str) -> SignalSnapshot | None:
        symbol = str(vt_symbol or "").strip()
        key = str(config_key or "").strip()
        pos_key = str(position_key or "").strip()
        if not symbol or not key or not pos_key:
            return None
        row = self.fetchone(
            select(wpc.c.payload)
            .where(
                wpc.c.vt_symbol == symbol,
                wpc.c.config_key == key,
                wpc.c.position_key == pos_key,
            )
            .order_by(wpc.c.updated_at.desc())
            .limit(1)
        )
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
        rows = self.fetchall(
            select(wpc.c.vt_symbol, wpc.c.bar_as_of, wpc.c.position_key, wpc.c.payload, wpc.c.updated_at).where(
                wpc.c.config_key == key,
                wpc.c.vt_symbol.in_(symbols),
            )
        )
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
        values = {
            "vt_symbol": symbol,
            "config_key": key,
            "bar_as_of": as_of,
            "position_key": pos_key,
            "payload": snapshot_to_payload(snapshot),
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        }

        def _write(conn) -> None:
            stmt = pg_insert(wpc).values(values)
            excluded = stmt.excluded
            conn.execute_stmt(
                stmt.on_conflict_do_update(
                    index_elements=[
                        wpc.c.vt_symbol,
                        wpc.c.config_key,
                        wpc.c.bar_as_of,
                        wpc.c.position_key,
                    ],
                    set_={"payload": excluded.payload, "updated_at": excluded.updated_at},
                )
            )

        self.run(_write)

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
        self.delete_matching()
