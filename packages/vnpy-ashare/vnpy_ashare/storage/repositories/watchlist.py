"""自选池 repository。"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from sqlalchemy import delete, insert
from vnpy.trader.constant import Exchange

from vnpy_ashare.storage.repository.app import AppUserScopedRepository
from vnpy_ashare.storage.repositories.csv_io import read_stock_csv_rows, write_stock_csv
from vnpy_ashare.storage.repositories.watchlist_groups import _prune_watchlist_group_members_conn
from vnpy_common.storage.tables import watchlist as wl
from vnpy_common.storage.tables import watchlist_group_members as wgm

WATCHLIST_MAX_ITEMS = 50

_WATCHLIST_COLUMNS = (wl.c.symbol, wl.c.exchange, wl.c.name)


def _normalize_watchlist_rows(items: list[tuple[str, Exchange, str]]) -> list[tuple[str, Exchange, str]]:
    seen: set[tuple[str, str]] = set()
    cleaned: list[tuple[str, Exchange, str]] = []
    for symbol, exchange, name in items:
        key = (symbol, exchange.name)
        if key in seen:
            continue
        seen.add(key)
        cleaned.append((symbol, exchange, name))
        if len(cleaned) >= WATCHLIST_MAX_ITEMS:
            break
    return cleaned


class WatchlistRepository(AppUserScopedRepository):
    table = wl

    @staticmethod
    def _row_to_stock(row) -> tuple[str, Exchange, str]:
        return row["symbol"], Exchange[row["exchange"]], row["name"]

    def _item_filter(self, symbol: str, exchange: Exchange):
        return (wl.c.symbol == symbol) & (wl.c.exchange == exchange.name)

    def load_rows(self) -> list[tuple[str, Exchange, str]]:
        rows = self.list_for_user(
            *_WATCHLIST_COLUMNS,
            order_by=(wl.c.sort_order, wl.c.symbol),
        )
        return [self._row_to_stock(row) for row in rows]

    def contains(self, symbol: str, exchange: Exchange) -> bool:
        return self.exists_for_user(self._item_filter(symbol, exchange))

    def item_count(self) -> int:
        return self.count_for_user()

    def at_capacity(self) -> bool:
        return self.item_count() >= WATCHLIST_MAX_ITEMS

    def add_failure_reason(self, symbol: str, exchange: Exchange) -> Literal["duplicate", "full"] | None:
        if self.contains(symbol, exchange):
            return "duplicate"
        if self.at_capacity():
            return "full"
        return None

    def add(self, symbol: str, exchange: Exchange, name: str = "") -> bool:
        if self.add_failure_reason(symbol, exchange) is not None:
            return False

        def _write(conn) -> None:
            self.insert_for_user(
                conn,
                symbol=symbol,
                exchange=exchange.name,
                name=name,
                sort_order=self.item_count(),
            )

        self.run(_write)
        return True

    def _insert_items(self, conn, items: list[tuple[str, Exchange, str]]) -> None:
        for index, (symbol, exchange, name) in enumerate(items):
            self.insert_for_user(
                conn,
                symbol=symbol,
                exchange=exchange.name,
                name=name,
                sort_order=index,
            )

    def _rewrite_order(self, conn, rows) -> None:
        self.delete_for_user(conn)
        uid = self.current_user_id()
        for index, row in enumerate(rows):
            conn.execute_stmt(
                insert(wl).values(
                    user_id=uid,
                    symbol=row["symbol"],
                    exchange=row["exchange"],
                    name=row["name"],
                    sort_order=index,
                )
            )

    def remove(self, symbol: str, exchange: Exchange) -> bool:
        def _write(conn) -> bool:
            rowcount = self.delete_where(conn, self.scope(self._item_filter(symbol, exchange)))
            if rowcount == 0:
                return False
            conn.execute_stmt(
                delete(wgm).where(
                    self.scope_table(
                        wgm,
                        (wgm.c.symbol == symbol) & (wgm.c.exchange == exchange.name),
                    )
                )
            )
            rows = conn.execute_stmt(
                self.select_columns(
                    *_WATCHLIST_COLUMNS,
                    where=(self.scope(),),
                    order_by=(wl.c.sort_order, wl.c.symbol),
                )
            ).fetchall()
            self._rewrite_order(conn, rows)
            return True

        return bool(self.run(_write))

    def clear(self) -> None:
        def _write(conn) -> None:
            conn.execute_stmt(delete(wgm).where(self.scope_table(wgm)))
            self.delete_for_user(conn)

        self.run(_write)

    def save_rows(self, items: list[tuple[str, Exchange, str]]) -> int:
        items = _normalize_watchlist_rows(items)

        def _write(conn) -> None:
            self.delete_for_user(conn)
            self._insert_items(conn, items)
            _prune_watchlist_group_members_conn(conn, self.current_user_id())

        self.run(_write)
        return len(items)

    def import_csv(self, path: Path) -> int:
        rows = read_stock_csv_rows(path)
        items = [(row["symbol"], Exchange[row["exchange"]], row.get("name", "")) for row in rows]
        return self.save_rows(_normalize_watchlist_rows(items))

    def move(self, symbol: str, exchange: Exchange, *, direction: Literal["up", "down"]) -> bool:
        items = self.load_rows()
        index = next(
            (idx for idx, (row_symbol, row_exchange, _name) in enumerate(items) if row_symbol == symbol and row_exchange == exchange),
            None,
        )
        if index is None:
            return False
        target = index - 1 if direction == "up" else index + 1
        if target < 0 or target >= len(items):
            return False
        items[index], items[target] = items[target], items[index]
        self.save_rows(items)
        return True


_repo = WatchlistRepository()


def load_watchlist_rows() -> list[tuple[str, Exchange, str]]:
    return _repo.load_rows()


def watchlist_contains(symbol: str, exchange: Exchange) -> bool:
    return _repo.contains(symbol, exchange)


def watchlist_item_count() -> int:
    return _repo.item_count()


def watchlist_at_capacity() -> bool:
    return _repo.at_capacity()


def watchlist_add_failure_reason(symbol: str, exchange: Exchange) -> Literal["duplicate", "full"] | None:
    return _repo.add_failure_reason(symbol, exchange)


def add_watchlist_item(symbol: str, exchange: Exchange, name: str = "") -> bool:
    return _repo.add(symbol, exchange, name)


def remove_watchlist_item(symbol: str, exchange: Exchange) -> bool:
    return _repo.remove(symbol, exchange)


def clear_watchlist() -> None:
    _repo.clear()


def save_watchlist_rows(items: list[tuple[str, Exchange, str]]) -> int:
    return _repo.save_rows(items)


def import_watchlist_csv(path: Path) -> int:
    return _repo.import_csv(path)


def export_watchlist_csv(path: Path) -> int:
    items = load_watchlist_rows()
    write_stock_csv(path, items)
    return len(items)


def move_watchlist_item(
    symbol: str,
    exchange: Exchange,
    *,
    direction: Literal["up", "down"],
) -> bool:
    return _repo.move(symbol, exchange, direction=direction)
