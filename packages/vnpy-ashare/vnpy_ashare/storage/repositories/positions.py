"""自选持仓 repository。"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from sqlalchemy import insert
from vnpy.trader.constant import Exchange

from vnpy_ashare.storage.repositories.watchlist import watchlist_contains
from vnpy_ashare.storage.repository.app import AppUserScopedRepository
from vnpy_common.storage.tables import watchlist_positions as wp

POSITION_MAX_ITEMS = 20

_POSITION_COLUMNS = (
    wp.c.symbol,
    wp.c.exchange,
    wp.c.cost_price,
    wp.c.volume,
    wp.c.buy_date,
    wp.c.notes,
    wp.c.source,
    wp.c.plan_pct,
    wp.c.sort_order,
    wp.c.created_at,
    wp.c.updated_at,
)


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


class PositionRepository(AppUserScopedRepository):
    table = wp

    @staticmethod
    def _row_to_position(row) -> dict[str, str | float | int | None]:
        plan_raw = row["plan_pct"] if "plan_pct" in row.keys() else None
        plan_pct = float(plan_raw) if plan_raw is not None else None
        return {
            "symbol": row["symbol"],
            "exchange": row["exchange"],
            "cost_price": float(row["cost_price"]),
            "volume": int(row["volume"]),
            "buy_date": row["buy_date"],
            "notes": row["notes"] or "",
            "source": row["source"] or "manual",
            "plan_pct": plan_pct,
            "sort_order": int(row["sort_order"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def _item_filter(self, symbol: str, exchange: Exchange):
        return (wp.c.symbol == symbol) & (wp.c.exchange == exchange.name)

    def load_rows(self) -> list[dict[str, str | float | int | None]]:
        rows = self.list_for_user(
            *_POSITION_COLUMNS,
            order_by=(wp.c.sort_order, wp.c.symbol),
        )
        return [self._row_to_position(row) for row in rows]

    def load_row(self, symbol: str, exchange: Exchange) -> dict[str, str | float | int | None] | None:
        rows = self.list_for_user(
            *_POSITION_COLUMNS,
            extras=(self._item_filter(symbol, exchange),),
            limit=1,
        )
        return self._row_to_position(rows[0]) if rows else None

    def item_count(self) -> int:
        return self.count_for_user()

    def at_capacity(self) -> bool:
        return self.item_count() >= POSITION_MAX_ITEMS

    def contains(self, symbol: str, exchange: Exchange) -> bool:
        return self.exists_for_user(self._item_filter(symbol, exchange))

    def add(
        self,
        symbol: str,
        exchange: Exchange,
        *,
        cost_price: float,
        volume: int,
        buy_date: str,
        notes: str = "",
        source: str = "manual",
        plan_pct: float | None = None,
    ) -> bool:
        if self.add_failure_reason(symbol, exchange) is not None:
            return False
        if cost_price <= 0 or volume <= 0:
            return False
        now = _now_iso()
        sort_order = self.item_count()

        def _write(conn) -> None:
            self.insert_for_user(
                conn,
                symbol=symbol,
                exchange=exchange.name,
                cost_price=cost_price,
                volume=volume,
                buy_date=buy_date,
                notes=notes,
                source=source,
                plan_pct=plan_pct,
                sort_order=sort_order,
                created_at=now,
                updated_at=now,
            )

        self.run(_write)
        return True

    def update(
        self,
        symbol: str,
        exchange: Exchange,
        *,
        cost_price: float,
        volume: int,
        buy_date: str,
        notes: str = "",
        plan_pct: float | None = None,
    ) -> bool:
        if not self.contains(symbol, exchange):
            return False
        if cost_price <= 0 or volume <= 0:
            return False
        now = _now_iso()
        rowcount = self.update_matching(
            {
                "cost_price": cost_price,
                "volume": volume,
                "buy_date": buy_date,
                "notes": notes,
                "plan_pct": plan_pct,
                "updated_at": now,
            },
            self.scope(self._item_filter(symbol, exchange)),
        )
        return rowcount > 0

    def _rewrite_order(self, conn, rows) -> None:
        uid = self.current_user_id()
        self.delete_for_user(conn)
        for index, row in enumerate(rows):
            conn.execute_stmt(
                insert(wp).values(
                    user_id=uid,
                    symbol=row["symbol"],
                    exchange=row["exchange"],
                    cost_price=row["cost_price"],
                    volume=row["volume"],
                    buy_date=row["buy_date"],
                    notes=row["notes"],
                    source=row["source"],
                    plan_pct=row["plan_pct"],
                    sort_order=index,
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                )
            )

    def remove(self, symbol: str, exchange: Exchange) -> bool:
        def _write(conn) -> bool:
            rowcount = self.delete_where(conn, self.scope(self._item_filter(symbol, exchange)))
            if rowcount == 0:
                return False
            rows = conn.execute_stmt(
                self.select_columns(
                    *_POSITION_COLUMNS,
                    where=(self.scope(),),
                    order_by=(wp.c.sort_order, wp.c.symbol),
                )
            ).fetchall()
            self._rewrite_order(conn, rows)
            return True

        return bool(self.run(_write))

    def clear(self) -> None:
        self.delete_all_for_user()

    def add_failure_reason(
        self,
        symbol: str,
        exchange: Exchange,
    ) -> Literal["duplicate", "full", "not_in_watchlist"] | None:
        if self.contains(symbol, exchange):
            return "duplicate"
        if self.at_capacity():
            return "full"
        if not watchlist_contains(symbol, exchange):
            return "not_in_watchlist"
        return None


_repo = PositionRepository()


def load_position_rows() -> list[dict[str, str | float | int | None]]:
    return _repo.load_rows()


def load_position_row(symbol: str, exchange: Exchange) -> dict[str, str | float | int | None] | None:
    return _repo.load_row(symbol, exchange)


def position_item_count() -> int:
    return _repo.item_count()


def position_at_capacity() -> bool:
    return _repo.at_capacity()


def position_contains(symbol: str, exchange: Exchange) -> bool:
    return _repo.contains(symbol, exchange)


def position_add_failure_reason(
    symbol: str,
    exchange: Exchange,
) -> Literal["duplicate", "full", "not_in_watchlist"] | None:
    return _repo.add_failure_reason(symbol, exchange)


def add_position_item(
    symbol: str,
    exchange: Exchange,
    *,
    cost_price: float,
    volume: int,
    buy_date: str,
    notes: str = "",
    source: str = "manual",
    plan_pct: float | None = None,
) -> bool:
    return _repo.add(
        symbol,
        exchange,
        cost_price=cost_price,
        volume=volume,
        buy_date=buy_date,
        notes=notes,
        source=source,
        plan_pct=plan_pct,
    )


def update_position_item(
    symbol: str,
    exchange: Exchange,
    *,
    cost_price: float,
    volume: int,
    buy_date: str,
    notes: str = "",
    plan_pct: float | None = None,
) -> bool:
    return _repo.update(
        symbol,
        exchange,
        cost_price=cost_price,
        volume=volume,
        buy_date=buy_date,
        notes=notes,
        plan_pct=plan_pct,
    )


def remove_position_item(symbol: str, exchange: Exchange) -> bool:
    return _repo.remove(symbol, exchange)


def clear_positions() -> None:
    _repo.clear()
