"""自选池 repository。"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from vnpy.trader.constant import Exchange

from vnpy_ashare.storage.connection import connect, init_app_db
from vnpy_ashare.storage.repositories.csv_io import read_stock_csv_rows, write_stock_csv
from vnpy_ashare.storage.repositories.watchlist_groups import _prune_watchlist_group_members_conn

WATCHLIST_MAX_ITEMS = 50


def _row_to_stock(row) -> tuple[str, Exchange, str]:
    return row["symbol"], Exchange[row["exchange"]], row["name"]


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


def load_watchlist_rows() -> list[tuple[str, Exchange, str]]:
    init_app_db()
    with connect() as conn:
        rows = conn.execute("SELECT symbol, exchange, name FROM watchlist ORDER BY sort_order, symbol").fetchall()
    return [_row_to_stock(row) for row in rows]


def watchlist_contains(symbol: str, exchange: Exchange) -> bool:
    init_app_db()
    with connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM watchlist WHERE symbol = ? AND exchange = ?",
            (symbol, exchange.name),
        ).fetchone()
    return row is not None


def watchlist_item_count() -> int:
    init_app_db()
    with connect() as conn:
        return int(conn.execute("SELECT COUNT(*) FROM watchlist").fetchone()[0])


def watchlist_at_capacity() -> bool:
    return watchlist_item_count() >= WATCHLIST_MAX_ITEMS


def watchlist_add_failure_reason(symbol: str, exchange: Exchange) -> Literal["duplicate", "full"] | None:
    if watchlist_contains(symbol, exchange):
        return "duplicate"
    if watchlist_at_capacity():
        return "full"
    return None


def add_watchlist_item(symbol: str, exchange: Exchange, name: str = "") -> bool:
    if watchlist_add_failure_reason(symbol, exchange) is not None:
        return False
    init_app_db()
    with connect() as conn:
        sort_order = conn.execute("SELECT COUNT(*) FROM watchlist").fetchone()[0]
        conn.execute(
            "INSERT INTO watchlist(symbol, exchange, name, sort_order) VALUES (?, ?, ?, ?)",
            (symbol, exchange.name, name, sort_order),
        )
    return True


def _rewrite_watchlist_order(conn, rows) -> None:
    conn.execute("DELETE FROM watchlist")
    for index, row in enumerate(rows):
        conn.execute(
            "INSERT INTO watchlist(symbol, exchange, name, sort_order) VALUES (?, ?, ?, ?)",
            (row["symbol"], row["exchange"], row["name"], index),
        )


def remove_watchlist_item(symbol: str, exchange: Exchange) -> bool:
    init_app_db()
    with connect() as conn:
        cursor = conn.execute(
            "DELETE FROM watchlist WHERE symbol = ? AND exchange = ?",
            (symbol, exchange.name),
        )
        if cursor.rowcount == 0:
            return False
        conn.execute(
            "DELETE FROM watchlist_group_members WHERE symbol = ? AND exchange = ?",
            (symbol, exchange.name),
        )
        rows = conn.execute("SELECT symbol, exchange, name FROM watchlist ORDER BY sort_order, symbol").fetchall()
        _rewrite_watchlist_order(conn, rows)
    return True


def clear_watchlist() -> None:
    init_app_db()
    with connect() as conn:
        conn.execute("DELETE FROM watchlist_group_members")
        conn.execute("DELETE FROM watchlist")


def save_watchlist_rows(items: list[tuple[str, Exchange, str]]) -> int:
    items = _normalize_watchlist_rows(items)
    init_app_db()
    with connect() as conn:
        conn.execute("DELETE FROM watchlist")
        for index, (symbol, exchange, name) in enumerate(items):
            conn.execute(
                "INSERT INTO watchlist(symbol, exchange, name, sort_order) VALUES (?, ?, ?, ?)",
                (symbol, exchange.name, name, index),
            )
        _prune_watchlist_group_members_conn(conn)
    return len(items)


def import_watchlist_csv(path: Path) -> int:
    init_app_db()
    rows = read_stock_csv_rows(path)
    items: list[tuple[str, Exchange, str]] = []
    for row in rows:
        items.append((row["symbol"], Exchange[row["exchange"]], row.get("name", "")))
    items = _normalize_watchlist_rows(items)
    with connect() as conn:
        conn.execute("DELETE FROM watchlist")
        for index, (symbol, exchange, name) in enumerate(items):
            conn.execute(
                "INSERT INTO watchlist(symbol, exchange, name, sort_order) VALUES (?, ?, ?, ?)",
                (symbol, exchange.name, name, index),
            )
        _prune_watchlist_group_members_conn(conn)
    return len(items)


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
    items = load_watchlist_rows()
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
    save_watchlist_rows(items)
    return True
