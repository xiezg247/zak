"""自选池 repository。"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from vnpy.trader.constant import Exchange

from vnpy_ashare.storage.connection import connect, init_app_db
from vnpy_ashare.storage.auth.scope import get_user_id
from vnpy_common.auth.scope import user_sql
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
    uid = get_user_id()
    with connect() as conn:
        rows = conn.execute(
            f"SELECT symbol, exchange, name FROM watchlist WHERE {user_sql()} ORDER BY sort_order, symbol",
            (uid,),
        ).fetchall()
    return [_row_to_stock(row) for row in rows]


def watchlist_contains(symbol: str, exchange: Exchange) -> bool:
    init_app_db()
    uid = get_user_id()
    with connect() as conn:
        row = conn.execute(
            f"SELECT 1 FROM watchlist WHERE {user_sql('symbol = ? AND exchange = ?')}",
            (uid, symbol, exchange.name),
        ).fetchone()
    return row is not None


def watchlist_item_count() -> int:
    init_app_db()
    uid = get_user_id()
    with connect() as conn:
        return int(conn.execute(f"SELECT COUNT(*) FROM watchlist WHERE {user_sql()}", (uid,)).fetchone()[0])


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
    uid = get_user_id()
    with connect() as conn:
        sort_order = conn.execute(f"SELECT COUNT(*) FROM watchlist WHERE {user_sql()}", (uid,)).fetchone()[0]
        conn.execute(
            "INSERT INTO watchlist(user_id, symbol, exchange, name, sort_order) VALUES (?, ?, ?, ?, ?)",
            (uid, symbol, exchange.name, name, sort_order),
        )
    return True


def _rewrite_watchlist_order(conn, uid: str, rows) -> None:
    conn.execute(f"DELETE FROM watchlist WHERE {user_sql()}", (uid,))
    for index, row in enumerate(rows):
        conn.execute(
            "INSERT INTO watchlist(user_id, symbol, exchange, name, sort_order) VALUES (?, ?, ?, ?, ?)",
            (uid, row["symbol"], row["exchange"], row["name"], index),
        )


def remove_watchlist_item(symbol: str, exchange: Exchange) -> bool:
    init_app_db()
    uid = get_user_id()
    with connect() as conn:
        cursor = conn.execute(
            f"DELETE FROM watchlist WHERE {user_sql('symbol = ? AND exchange = ?')}",
            (uid, symbol, exchange.name),
        )
        if cursor.rowcount == 0:
            return False
        conn.execute(
            f"DELETE FROM watchlist_group_members WHERE {user_sql('symbol = ? AND exchange = ?')}",
            (uid, symbol, exchange.name),
        )
        rows = conn.execute(
            f"SELECT symbol, exchange, name FROM watchlist WHERE {user_sql()} ORDER BY sort_order, symbol",
            (uid,),
        ).fetchall()
        _rewrite_watchlist_order(conn, uid, rows)
    return True


def clear_watchlist() -> None:
    init_app_db()
    uid = get_user_id()
    with connect() as conn:
        conn.execute(f"DELETE FROM watchlist_group_members WHERE {user_sql()}", (uid,))
        conn.execute(f"DELETE FROM watchlist WHERE {user_sql()}", (uid,))


def save_watchlist_rows(items: list[tuple[str, Exchange, str]]) -> int:
    items = _normalize_watchlist_rows(items)
    init_app_db()
    uid = get_user_id()
    with connect() as conn:
        conn.execute(f"DELETE FROM watchlist WHERE {user_sql()}", (uid,))
        for index, (symbol, exchange, name) in enumerate(items):
            conn.execute(
                "INSERT INTO watchlist(user_id, symbol, exchange, name, sort_order) VALUES (?, ?, ?, ?, ?)",
                (uid, symbol, exchange.name, name, index),
            )
        _prune_watchlist_group_members_conn(conn, uid)
    return len(items)


def import_watchlist_csv(path: Path) -> int:
    init_app_db()
    uid = get_user_id()
    rows = read_stock_csv_rows(path)
    items: list[tuple[str, Exchange, str]] = []
    for row in rows:
        items.append((row["symbol"], Exchange[row["exchange"]], row.get("name", "")))
    items = _normalize_watchlist_rows(items)
    with connect() as conn:
        conn.execute(f"DELETE FROM watchlist WHERE {user_sql()}", (uid,))
        for index, (symbol, exchange, name) in enumerate(items):
            conn.execute(
                "INSERT INTO watchlist(user_id, symbol, exchange, name, sort_order) VALUES (?, ?, ?, ?, ?)",
                (uid, symbol, exchange.name, name, index),
            )
        _prune_watchlist_group_members_conn(conn, uid)
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
