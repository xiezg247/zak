"""项目元数据 SQLite：自选池、全 A 股列表（与 VeighNa K 线库分离）"""

from __future__ import annotations

import csv
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path

from typing import Literal

from vnpy.trader.constant import Exchange

from vnpy_ashare.paths import APP_DB_PATH
UNIVERSE_SYNCED_AT_KEY = "universe_synced_at"
CACHE_MAX_AGE = timedelta(days=7)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS watchlist (
    symbol TEXT NOT NULL,
    exchange TEXT NOT NULL,
    name TEXT NOT NULL DEFAULT '',
    sort_order INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (symbol, exchange)
);

CREATE TABLE IF NOT EXISTS universe (
    symbol TEXT NOT NULL,
    exchange TEXT NOT NULL,
    name TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (symbol, exchange)
);

CREATE INDEX IF NOT EXISTS idx_universe_symbol ON universe(symbol);

CREATE TABLE IF NOT EXISTS trade_calendar (
    cal_date TEXT PRIMARY KEY,
    is_open INTEGER NOT NULL
);
"""


@contextmanager
def _connect():
    APP_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(APP_DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_app_db() -> Path:
    """初始化数据库表结构。"""
    with _connect() as conn:
        conn.executescript(_SCHEMA)
    return APP_DB_PATH


def _set_meta(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO meta(key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )


def _get_meta(conn: sqlite3.Connection, key: str) -> str | None:
    row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None


def get_meta(key: str) -> str | None:
    init_app_db()
    with _connect() as conn:
        return _get_meta(conn, key)


def set_meta(key: str, value: str) -> None:
    init_app_db()
    with _connect() as conn:
        _set_meta(conn, key, value)


def _import_watchlist_csv(conn: sqlite3.Connection, path: Path) -> int:
    rows = _read_csv_rows(path)
    conn.execute("DELETE FROM watchlist")
    for index, row in enumerate(rows):
        conn.execute(
            "INSERT INTO watchlist(symbol, exchange, name, sort_order) VALUES (?, ?, ?, ?)",
            (row["symbol"], row["exchange"], row.get("name", ""), index),
        )
    return len(rows)


def _import_universe_csv(conn: sqlite3.Connection, path: Path) -> int:
    rows = _read_csv_rows(path)
    conn.execute("DELETE FROM universe")
    conn.executemany(
        "INSERT INTO universe(symbol, exchange, name) VALUES (?, ?, ?)",
        [(row["symbol"], row["exchange"], row.get("name", "")) for row in rows],
    )
    return len(rows)


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    with path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            items.append(
                {
                    "symbol": row["symbol"].strip(),
                    "exchange": row["exchange"].strip().upper(),
                    "name": row.get("name", "").strip(),
                }
            )
    return items


def _row_to_stock(row: sqlite3.Row) -> tuple[str, Exchange, str]:
    return row["symbol"], Exchange[row["exchange"]], row["name"]


def load_watchlist_rows() -> list[tuple[str, Exchange, str]]:
    init_app_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT symbol, exchange, name FROM watchlist ORDER BY sort_order, symbol"
        ).fetchall()
    return [_row_to_stock(row) for row in rows]


def watchlist_contains(symbol: str, exchange: Exchange) -> bool:
    init_app_db()
    with _connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM watchlist WHERE symbol = ? AND exchange = ?",
            (symbol, exchange.name),
        ).fetchone()
    return row is not None


def add_watchlist_item(symbol: str, exchange: Exchange, name: str = "") -> bool:
    """加入自选池，已存在则返回 False。"""
    init_app_db()
    with _connect() as conn:
        if conn.execute(
            "SELECT 1 FROM watchlist WHERE symbol = ? AND exchange = ?",
            (symbol, exchange.name),
        ).fetchone():
            return False
        sort_order = conn.execute("SELECT COUNT(*) FROM watchlist").fetchone()[0]
        conn.execute(
            "INSERT INTO watchlist(symbol, exchange, name, sort_order) VALUES (?, ?, ?, ?)",
            (symbol, exchange.name, name, sort_order),
        )
    return True


def remove_watchlist_item(symbol: str, exchange: Exchange) -> bool:
    """移出自选池，不存在则返回 False。"""
    init_app_db()
    with _connect() as conn:
        cursor = conn.execute(
            "DELETE FROM watchlist WHERE symbol = ? AND exchange = ?",
            (symbol, exchange.name),
        )
        if cursor.rowcount == 0:
            return False
        rows = conn.execute(
            "SELECT symbol, exchange, name FROM watchlist ORDER BY sort_order, symbol"
        ).fetchall()
        conn.execute("DELETE FROM watchlist")
        for index, row in enumerate(rows):
            conn.execute(
                "INSERT INTO watchlist(symbol, exchange, name, sort_order) VALUES (?, ?, ?, ?)",
                (row["symbol"], row["exchange"], row["name"], index),
            )
    return True


def clear_watchlist() -> None:
    """清空自选池。"""
    init_app_db()
    with _connect() as conn:
        conn.execute("DELETE FROM watchlist")


def save_watchlist_rows(items: list[tuple[str, Exchange, str]]) -> int:
    init_app_db()
    with _connect() as conn:
        conn.execute("DELETE FROM watchlist")
        for index, (symbol, exchange, name) in enumerate(items):
            conn.execute(
                "INSERT INTO watchlist(symbol, exchange, name, sort_order) VALUES (?, ?, ?, ?)",
                (symbol, exchange.name, name, index),
            )
    return len(items)


def import_watchlist_csv(path: Path) -> int:
    init_app_db()
    with _connect() as conn:
        return _import_watchlist_csv(conn, path)


def export_watchlist_csv(path: Path) -> int:
    items = load_watchlist_rows()
    _write_stock_csv(path, items)
    return len(items)


def import_universe_csv(path: Path) -> int:
    init_app_db()
    with _connect() as conn:
        count = _import_universe_csv(conn, path)
        mtime = datetime.fromtimestamp(path.stat().st_mtime)
        _set_meta(conn, UNIVERSE_SYNCED_AT_KEY, mtime.isoformat())
    return count


def export_universe_csv(path: Path) -> int:
    items = load_universe_rows()
    _write_stock_csv(path, items)
    return len(items)


def _write_stock_csv(
    path: Path,
    items: list[tuple[str, Exchange, str]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["symbol", "exchange", "name"])
        for symbol, exchange, name in items:
            writer.writerow([symbol, exchange.name, name])


def load_universe_page(
    *,
    offset: int = 0,
    limit: int = 50,
) -> tuple[list[tuple[str, Exchange, str]], int]:
    """分页读取全 A 股列表（按证券代码升序）。"""
    init_app_db()
    with _connect() as conn:
        total = conn.execute("SELECT COUNT(*) FROM universe").fetchone()[0]
        rows = conn.execute(
            "SELECT symbol, exchange, name FROM universe "
            "ORDER BY symbol LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
    return [_row_to_stock(row) for row in rows], int(total)


def move_watchlist_item(
    symbol: str,
    exchange: Exchange,
    *,
    direction: Literal["up", "down"],
) -> bool:
    """调整自选池顺序（按加入先后，上移/下移一行）。"""
    items = load_watchlist_rows()
    index = next(
        (
            idx
            for idx, (row_symbol, row_exchange, _name) in enumerate(items)
            if row_symbol == symbol and row_exchange == exchange
        ),
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


def load_universe_rows() -> list[tuple[str, Exchange, str]]:
    init_app_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT symbol, exchange, name FROM universe ORDER BY symbol"
        ).fetchall()
    return [_row_to_stock(row) for row in rows]


def build_symbol_name_map() -> dict[tuple[str, Exchange], str]:
    """证券代码 → 名称；优先 universe，自选池作补充。"""
    mapping: dict[tuple[str, Exchange], str] = {}
    for symbol, exchange, name in load_universe_rows():
        if name:
            mapping[(symbol, exchange)] = name
    for symbol, exchange, name in load_watchlist_rows():
        key = (symbol, exchange)
        if name and key not in mapping:
            mapping[key] = name
    return mapping


def save_universe_rows(
    items: list[tuple[str, Exchange, str]],
    *,
    synced_at: datetime | None = None,
) -> int:
    init_app_db()
    synced_at = synced_at or datetime.now()
    with _connect() as conn:
        conn.execute("DELETE FROM universe")
        conn.executemany(
            "INSERT INTO universe(symbol, exchange, name) VALUES (?, ?, ?)",
            [(symbol, exchange.name, name) for symbol, exchange, name in items],
        )
        _set_meta(conn, UNIVERSE_SYNCED_AT_KEY, synced_at.isoformat())
    return len(items)


def universe_exists() -> bool:
    init_app_db()
    with _connect() as conn:
        count = conn.execute("SELECT COUNT(*) FROM universe").fetchone()[0]
    return count > 0


def universe_count() -> int:
    init_app_db()
    with _connect() as conn:
        return conn.execute("SELECT COUNT(*) FROM universe").fetchone()[0]


def search_universe(
    keyword: str,
    *,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[tuple[str, Exchange, str]], int]:
    """按代码/名称搜索全 A 股，返回 (结果, 总数)。"""
    init_app_db()
    keyword = keyword.strip().lower()
    if not keyword:
        return [], 0

    pattern = f"%{keyword}%"
    with _connect() as conn:
        total = conn.execute(
            "SELECT COUNT(*) FROM universe "
            "WHERE lower(symbol) LIKE ? OR lower(name) LIKE ?",
            (pattern, pattern),
        ).fetchone()[0]
        rows = conn.execute(
            "SELECT symbol, exchange, name FROM universe "
            "WHERE lower(symbol) LIKE ? OR lower(name) LIKE ? "
            "ORDER BY symbol LIMIT ? OFFSET ?",
            (pattern, pattern, limit, offset),
        ).fetchall()
    return [_row_to_stock(row) for row in rows], int(total)


def universe_is_fresh(max_age: timedelta = CACHE_MAX_AGE) -> bool:
    init_app_db()
    with _connect() as conn:
        if conn.execute("SELECT COUNT(*) FROM universe").fetchone()[0] == 0:
            return False
        synced_at_raw = _get_meta(conn, UNIVERSE_SYNCED_AT_KEY)
    if not synced_at_raw:
        return False
    synced_at = datetime.fromisoformat(synced_at_raw)
    return datetime.now() - synced_at < max_age
