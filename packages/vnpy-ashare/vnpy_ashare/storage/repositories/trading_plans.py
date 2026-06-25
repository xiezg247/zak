"""交易计划 repository（J-01）。"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import delete, insert, select, update
from vnpy.trader.constant import Exchange

from vnpy_ashare.domain.trading.plan import TradingPlanRecord, TradingPlanSymbolRecord
from vnpy_ashare.storage.repository.app import AppUserScopedRepository
from vnpy_common.storage.tables import trading_plan_symbols as tps
from vnpy_common.storage.tables import trading_plans as tp

PLAN_MAX_SYMBOLS = 5

PlanSymbolRow = tuple[str, Exchange] | tuple[str, Exchange, tuple[str, ...] | None]

_SYMBOL_COLUMNS = (
    tps.c.symbol,
    tps.c.exchange,
    tps.c.allowed_modes,
    tps.c.entry_conditions,
    tps.c.exit_conditions,
    tps.c.sort_order,
)


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _parse_modes(text: str) -> tuple[str, ...]:
    parts = [item.strip() for item in str(text or "").split(",") if item.strip()]
    return tuple(parts)


def _modes_to_text(modes: tuple[str, ...] | list[str]) -> str:
    return ",".join(item.strip() for item in modes if item.strip())


def _row_to_symbol(row, *, sort_order: int) -> TradingPlanSymbolRecord:
    return TradingPlanSymbolRecord(
        symbol=str(row["symbol"]),
        exchange=str(row["exchange"]),
        allowed_modes=_parse_modes(row["allowed_modes"]),
        entry_conditions=str(row["entry_conditions"] or ""),
        exit_conditions=str(row["exit_conditions"] or ""),
        sort_order=int(row["sort_order"]) if "sort_order" in row.keys() else sort_order,
    )


def _row_to_plan(row, symbols: tuple[TradingPlanSymbolRecord, ...]) -> TradingPlanRecord:
    return TradingPlanRecord(
        id=str(row["id"]),
        trade_date=str(row["trade_date"]),
        emotion_expected=str(row["emotion_expected"] or ""),
        max_position_pct=float(row["max_position_pct"] or 0),
        notes=str(row["notes"] or ""),
        status=str(row["status"]),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
        symbols=symbols,
    )


class TradingPlanRepository(AppUserScopedRepository):
    table = tp

    def _load_symbols(self, conn, plan_id: str) -> tuple[TradingPlanSymbolRecord, ...]:
        rows = conn.execute_stmt(
            select(*_SYMBOL_COLUMNS, tps.c.plan_id).where(self.scope_table(tps, tps.c.plan_id == plan_id)).order_by(tps.c.sort_order, tps.c.symbol)
        ).fetchall()
        return tuple(_row_to_symbol(row, sort_order=index) for index, row in enumerate(rows))

    def _batch_load_symbols(self, conn, plan_ids: list[str]) -> dict[str, tuple[TradingPlanSymbolRecord, ...]]:
        if not plan_ids:
            return {}
        rows = conn.execute_stmt(
            select(tps.c.plan_id, *_SYMBOL_COLUMNS)
            .where(self.scope_table(tps, tps.c.plan_id.in_(plan_ids)))
            .order_by(tps.c.plan_id, tps.c.sort_order, tps.c.symbol)
        ).fetchall()
        by_plan: dict[str, list[TradingPlanSymbolRecord]] = {}
        for row in rows:
            pid = str(row["plan_id"])
            by_plan.setdefault(pid, []).append(_row_to_symbol(row, sort_order=len(by_plan[pid])))
        return {pid: tuple(items) for pid, items in by_plan.items()}

    def _replace_symbols(self, conn, plan_id: str, symbols: Sequence[PlanSymbolRow]) -> None:
        conn.execute_stmt(delete(tps).where(self.scope_table(tps, tps.c.plan_id == plan_id)))
        if not symbols:
            return
        uid = self.current_user_id()
        for index, item in enumerate(symbols[:PLAN_MAX_SYMBOLS]):
            if len(item) == 2:
                symbol, exchange = item
                modes: tuple[str, ...] = ()
            else:
                symbol, exchange, modes_raw = item
                modes = tuple(modes_raw) if modes_raw else ()
            conn.execute_stmt(
                insert(tps).values(
                    user_id=uid,
                    plan_id=plan_id,
                    symbol=symbol,
                    exchange=exchange.name,
                    allowed_modes=_modes_to_text(modes or ()),
                    entry_conditions="",
                    exit_conditions="",
                    sort_order=index,
                )
            )

    def load_plan(self, plan_id: str) -> TradingPlanRecord | None:
        def _write(conn):
            row = conn.execute_stmt(select(tp).where(self.scope(tp.c.id == plan_id))).fetchone()
            if row is None:
                return None
            symbols = self._load_symbols(conn, plan_id)
            return _row_to_plan(row, symbols)

        return self.run(_write)

    def load_active_plan(self, trade_date: str) -> TradingPlanRecord | None:
        def _write(conn):
            row = conn.execute_stmt(
                select(tp).where(self.scope((tp.c.trade_date == trade_date[:10]) & (tp.c.status == "active"))).order_by(tp.c.updated_at.desc()).limit(1)
            ).fetchone()
            if row is None:
                return None
            plan_id = str(row["id"])
            symbols = self._load_symbols(conn, plan_id)
            return _row_to_plan(row, symbols)

        return self.run(_write)

    def list_plans(self, *, limit: int = 20) -> list[TradingPlanRecord]:
        def _write(conn):
            rows = conn.execute_stmt(select(tp).where(self.scope()).order_by(tp.c.trade_date.desc(), tp.c.updated_at.desc()).limit(max(1, limit))).fetchall()
            if not rows:
                return []
            plan_ids = [str(row["id"]) for row in rows]
            symbols_map = self._batch_load_symbols(conn, plan_ids)
            return [_row_to_plan(row, symbols_map.get(str(row["id"]), ())) for row in rows]

        return self.run(_write)

    def create_plan(
        self,
        *,
        trade_date: str,
        emotion_expected: str = "",
        max_position_pct: float = 0.0,
        notes: str = "",
        status: str = "draft",
        symbols: list[tuple[str, Exchange]] | None = None,
    ) -> str | None:
        normalized_date = trade_date[:10]
        if not normalized_date:
            return None
        plan_id = uuid.uuid4().hex
        now = _now_iso()

        def _write(conn) -> None:
            self.insert_for_user(
                conn,
                id=plan_id,
                trade_date=normalized_date,
                emotion_expected=emotion_expected.strip(),
                max_position_pct=max(0.0, min(float(max_position_pct), 1.0)),
                notes=notes.strip(),
                status=status,
                created_at=now,
                updated_at=now,
            )
            if symbols:
                self._replace_symbols(conn, plan_id, symbols)

        self.run(_write)
        return plan_id

    def update_meta(
        self,
        plan_id: str,
        *,
        emotion_expected: str | None = None,
        max_position_pct: float | None = None,
        notes: str | None = None,
        status: str | None = None,
    ) -> bool:
        values: dict[str, object] = {}
        if emotion_expected is not None:
            values["emotion_expected"] = emotion_expected.strip()
        if max_position_pct is not None:
            values["max_position_pct"] = max(0.0, min(float(max_position_pct), 1.0))
        if notes is not None:
            values["notes"] = notes.strip()
        if status is not None:
            values["status"] = status
        if not values:
            return False
        values["updated_at"] = _now_iso()
        return self.update_matching(values, self.scope(tp.c.id == plan_id)) > 0

    def replace_symbols(self, plan_id: str, symbols: list[tuple[str, Exchange]]) -> bool:
        if not self.exists_for_user(tp.c.id == plan_id):
            return False

        def _write(conn) -> None:
            self._replace_symbols(
                conn,
                plan_id,
                [(symbol, exchange) for symbol, exchange in symbols[:PLAN_MAX_SYMBOLS]],
            )

        self.run(_write)
        return True

    def activate_plan(self, plan_id: str) -> bool:
        def _write(conn) -> bool:
            row = conn.execute_stmt(select(tp.c.trade_date).where(self.scope(tp.c.id == plan_id))).fetchone()
            if row is None:
                return False
            trade_date = str(row["trade_date"])
            now = _now_iso()
            conn.execute_stmt(
                update(tp).where(self.scope((tp.c.trade_date == trade_date) & (tp.c.status == "active"))).values(status="archived", updated_at=now)
            )
            cursor = conn.execute_stmt(update(tp).where(self.scope(tp.c.id == plan_id)).values(status="active", updated_at=now))
            return bool(cursor.rowcount > 0)

        return bool(self.run(_write))


_repo = TradingPlanRepository()


def load_trading_plan(plan_id: str) -> TradingPlanRecord | None:
    return _repo.load_plan(plan_id)


def load_active_trading_plan(trade_date: str) -> TradingPlanRecord | None:
    return _repo.load_active_plan(trade_date)


def list_trading_plans(*, limit: int = 20) -> list[TradingPlanRecord]:
    return _repo.list_plans(limit=limit)


def create_trading_plan(
    *,
    trade_date: str,
    emotion_expected: str = "",
    max_position_pct: float = 0.0,
    notes: str = "",
    status: str = "draft",
    symbols: list[tuple[str, Exchange]] | None = None,
) -> str | None:
    return _repo.create_plan(
        trade_date=trade_date,
        emotion_expected=emotion_expected,
        max_position_pct=max_position_pct,
        notes=notes,
        status=status,
        symbols=symbols,
    )


def update_trading_plan_meta(
    plan_id: str,
    *,
    emotion_expected: str | None = None,
    max_position_pct: float | None = None,
    notes: str | None = None,
    status: str | None = None,
) -> bool:
    return _repo.update_meta(
        plan_id,
        emotion_expected=emotion_expected,
        max_position_pct=max_position_pct,
        notes=notes,
        status=status,
    )


def replace_trading_plan_symbols(plan_id: str, symbols: list[tuple[str, Exchange]]) -> bool:
    return _repo.replace_symbols(plan_id, symbols)


def activate_trading_plan(plan_id: str) -> bool:
    return _repo.activate_plan(plan_id)
