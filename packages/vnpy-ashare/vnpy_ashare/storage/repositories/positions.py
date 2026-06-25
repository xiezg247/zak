"""自选持仓 repository。"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from vnpy.trader.constant import Exchange

from vnpy_ashare.storage.auth.scope import get_user_id
from vnpy_ashare.storage.connection import connect, init_app_db
from vnpy_ashare.storage.repositories.watchlist import watchlist_contains
from vnpy_common.auth.scope import user_sql

POSITION_MAX_ITEMS = 20


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


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


def load_position_rows() -> list[dict[str, str | float | int | None]]:
    init_app_db()
    uid = get_user_id()
    with connect() as conn:
        rows = conn.execute(
            f"""
            SELECT symbol, exchange, cost_price, volume, buy_date, notes, source, plan_pct, sort_order, created_at, updated_at
            FROM watchlist_positions WHERE {user_sql()} ORDER BY sort_order, symbol
            """,
            (uid,),
        ).fetchall()
    return [_row_to_position(row) for row in rows]


def load_position_row(symbol: str, exchange: Exchange) -> dict[str, str | float | int | None] | None:
    init_app_db()
    uid = get_user_id()
    with connect() as conn:
        row = conn.execute(
            f"""
            SELECT symbol, exchange, cost_price, volume, buy_date, notes, source, plan_pct, sort_order, created_at, updated_at
            FROM watchlist_positions WHERE {user_sql("symbol = ? AND exchange = ?")}
            """,
            (uid, symbol, exchange.name),
        ).fetchone()
    return _row_to_position(row) if row is not None else None


def position_item_count() -> int:
    init_app_db()
    uid = get_user_id()
    with connect() as conn:
        return int(conn.execute(f"SELECT COUNT(*) FROM watchlist_positions WHERE {user_sql()}", (uid,)).fetchone()[0])


def position_at_capacity() -> bool:
    return position_item_count() >= POSITION_MAX_ITEMS


def position_contains(symbol: str, exchange: Exchange) -> bool:
    init_app_db()
    uid = get_user_id()
    with connect() as conn:
        row = conn.execute(
            f"SELECT 1 FROM watchlist_positions WHERE {user_sql('symbol = ? AND exchange = ?')}",
            (uid, symbol, exchange.name),
        ).fetchone()
    return row is not None


def position_add_failure_reason(symbol: str, exchange: Exchange) -> Literal["duplicate", "full", "not_in_watchlist"] | None:
    if position_contains(symbol, exchange):
        return "duplicate"
    if position_at_capacity():
        return "full"
    if not watchlist_contains(symbol, exchange):
        return "not_in_watchlist"
    return None


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
    if position_add_failure_reason(symbol, exchange) is not None:
        return False
    if cost_price <= 0 or volume <= 0:
        return False
    now = _now_iso()
    init_app_db()
    uid = get_user_id()
    with connect() as conn:
        sort_order = conn.execute(f"SELECT COUNT(*) FROM watchlist_positions WHERE {user_sql()}", (uid,)).fetchone()[0]
        conn.execute(
            "INSERT INTO watchlist_positions(user_id, symbol, exchange, cost_price, volume, buy_date, notes, source, plan_pct, sort_order, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (uid, symbol, exchange.name, cost_price, volume, buy_date, notes, source, plan_pct, sort_order, now, now),
        )
    return True


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
    if not position_contains(symbol, exchange):
        return False
    if cost_price <= 0 or volume <= 0:
        return False
    now = _now_iso()
    init_app_db()
    uid = get_user_id()
    with connect() as conn:
        cursor = conn.execute(
            f"UPDATE watchlist_positions SET cost_price = ?, volume = ?, buy_date = ?, notes = ?, plan_pct = ?, updated_at = ? WHERE {user_sql('symbol = ? AND exchange = ?')}",
            (cost_price, volume, buy_date, notes, plan_pct, now, uid, symbol, exchange.name),
        )
        return bool(cursor.rowcount > 0)


def _rewrite_position_order(conn, uid: str, rows) -> None:
    conn.execute(f"DELETE FROM watchlist_positions WHERE {user_sql()}", (uid,))
    for index, row in enumerate(rows):
        conn.execute(
            "INSERT INTO watchlist_positions(user_id, symbol, exchange, cost_price, volume, buy_date, notes, source, plan_pct, sort_order, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                uid,
                row["symbol"],
                row["exchange"],
                row["cost_price"],
                row["volume"],
                row["buy_date"],
                row["notes"],
                row["source"],
                row["plan_pct"],
                index,
                row["created_at"],
                row["updated_at"],
            ),
        )


def remove_position_item(symbol: str, exchange: Exchange) -> bool:
    init_app_db()
    uid = get_user_id()
    with connect() as conn:
        cursor = conn.execute(
            f"DELETE FROM watchlist_positions WHERE {user_sql('symbol = ? AND exchange = ?')}",
            (uid, symbol, exchange.name),
        )
        if cursor.rowcount == 0:
            return False
        rows = conn.execute(
            f"""
            SELECT symbol, exchange, cost_price, volume, buy_date, notes, source, plan_pct, sort_order, created_at, updated_at
            FROM watchlist_positions WHERE {user_sql()} ORDER BY sort_order, symbol
            """,
            (uid,),
        ).fetchall()
        _rewrite_position_order(conn, uid, rows)
    return True


def clear_positions() -> None:
    init_app_db()
    uid = get_user_id()
    with connect() as conn:
        conn.execute(f"DELETE FROM watchlist_positions WHERE {user_sql()}", (uid,))
