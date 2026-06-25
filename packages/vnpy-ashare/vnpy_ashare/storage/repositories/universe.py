"""全 A 股 universe repository。"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from vnpy.trader.constant import Exchange

from vnpy_ashare.storage.connection import _get_meta, _set_meta, connect, init_app_db
from vnpy_ashare.storage.repositories.csv_io import read_stock_csv_rows, write_stock_csv

UNIVERSE_SYNCED_AT_KEY = "universe_synced_at"
CACHE_MAX_AGE = timedelta(days=7)


def _row_to_stock(row) -> tuple[str, Exchange, str]:
    return row["symbol"], Exchange[row["exchange"]], row["name"]


def _board_where_clause(board: str | None) -> tuple[str, list[str]]:
    """板块过滤 SQL；LIKE 模式必须参数化，避免 PostgreSQL 将 % 解析为占位符。"""
    if not board or board == "全部":
        return "", []
    board_prefixes: dict[str, tuple[str, ...]] = {
        "沪深主板": ("600", "601", "603", "000", "001", "002", "003"),
        "创业板": ("300",),
        "科创板": ("688",),
        "北交所": ("8", "4"),
    }
    prefixes = board_prefixes.get(board)
    if not prefixes:
        return "", []
    conditions = ["symbol LIKE ?" for _ in prefixes]
    params = [f"{prefix}%" for prefix in prefixes]
    return f" AND ({' OR '.join(conditions)})", params


def count_universe(board: str | None = None) -> int:
    init_app_db()
    board_sql, board_params = _board_where_clause(board)
    with connect() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) FROM universe WHERE 1=1{board_sql}",
            board_params,
        ).fetchone()[0]
    return int(total)


def load_universe_slice(
    *,
    offset: int = 0,
    limit: int = 50,
    board: str | None = None,
) -> list[tuple[str, Exchange, str]]:
    init_app_db()
    board_sql, board_params = _board_where_clause(board)
    with connect() as conn:
        rows = conn.execute(
            f"SELECT symbol, exchange, name FROM universe WHERE 1=1{board_sql} ORDER BY symbol LIMIT ? OFFSET ?",
            (*board_params, limit, offset),
        ).fetchall()
    return [_row_to_stock(row) for row in rows]


def load_universe_page(
    *,
    offset: int = 0,
    limit: int = 50,
    board: str | None = None,
) -> tuple[list[tuple[str, Exchange, str]], int]:
    total = count_universe(board)
    rows = load_universe_slice(offset=offset, limit=limit, board=board)
    return rows, total


def load_universe_rows() -> list[tuple[str, Exchange, str]]:
    init_app_db()
    with connect() as conn:
        rows = conn.execute("SELECT symbol, exchange, name FROM universe ORDER BY symbol").fetchall()
    return [_row_to_stock(row) for row in rows]


def load_universe_names_for_keys(
    keys: list[tuple[str, Exchange]],
    *,
    chunk_size: int = 400,
) -> dict[tuple[str, Exchange], str]:
    """按 (symbol, exchange) 批量查名称；分页本地列表避免全表 load_universe_rows。"""
    if not keys:
        return {}
    init_app_db()
    unique_keys = list(dict.fromkeys(keys))
    result: dict[tuple[str, Exchange], str] = {}
    with connect() as conn:
        for start in range(0, len(unique_keys), chunk_size):
            chunk = unique_keys[start : start + chunk_size]
            placeholders = ",".join("(?, ?)" for _ in chunk)
            params = [part for symbol, exchange in chunk for part in (symbol, exchange.name)]
            rows = conn.execute(
                f"SELECT symbol, exchange, name FROM universe WHERE (symbol, exchange) IN ({placeholders})",
                params,
            ).fetchall()
            for row in rows:
                result[(row["symbol"], Exchange[row["exchange"]])] = row["name"]
    return result


def save_universe_rows(
    items: list[tuple[str, Exchange, str]],
    *,
    synced_at: datetime | None = None,
) -> int:
    init_app_db()
    synced_at = synced_at or datetime.now()
    with connect() as conn:
        conn.execute("DELETE FROM universe")
        conn.executemany(
            "INSERT INTO universe(symbol, exchange, name) VALUES (?, ?, ?)",
            [(symbol, exchange.name, name) for symbol, exchange, name in items],
        )
        _set_meta(conn, UNIVERSE_SYNCED_AT_KEY, synced_at.isoformat())
    return len(items)


def universe_exists() -> bool:
    init_app_db()
    with connect() as conn:
        count = conn.execute("SELECT COUNT(*) FROM universe").fetchone()[0]
    return int(count) > 0


def universe_count() -> int:
    init_app_db()
    with connect() as conn:
        return int(conn.execute("SELECT COUNT(*) FROM universe").fetchone()[0])


def search_universe(
    keyword: str,
    *,
    limit: int = 50,
    offset: int = 0,
    board: str | None = None,
) -> tuple[list[tuple[str, Exchange, str]], int]:
    init_app_db()
    keyword = keyword.strip().lower()
    if not keyword:
        return [], 0

    pattern = f"%{keyword}%"
    board_sql, board_params = _board_where_clause(board)
    with connect() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) FROM universe WHERE (lower(symbol) LIKE ? OR lower(name) LIKE ?){board_sql}",
            (pattern, pattern, *board_params),
        ).fetchone()[0]
        rows = conn.execute(
            f"SELECT symbol, exchange, name FROM universe WHERE (lower(symbol) LIKE ? OR lower(name) LIKE ?){board_sql} ORDER BY symbol LIMIT ? OFFSET ?",
            (pattern, pattern, *board_params, limit, offset),
        ).fetchall()
    return [_row_to_stock(row) for row in rows], int(total)


def universe_is_fresh(max_age: timedelta = CACHE_MAX_AGE) -> bool:
    init_app_db()
    with connect() as conn:
        if conn.execute("SELECT COUNT(*) FROM universe").fetchone()[0] == 0:
            return False
        synced_at_raw = _get_meta(conn, UNIVERSE_SYNCED_AT_KEY)
    if not synced_at_raw:
        return False
    synced_at = datetime.fromisoformat(synced_at_raw)
    return datetime.now() - synced_at < max_age


def import_universe_csv(path: Path) -> int:
    init_app_db()
    rows = read_stock_csv_rows(path)
    with connect() as conn:
        conn.execute("DELETE FROM universe")
        conn.executemany(
            "INSERT INTO universe(symbol, exchange, name) VALUES (?, ?, ?)",
            [(row["symbol"], row["exchange"], row.get("name", "")) for row in rows],
        )
        mtime = datetime.fromtimestamp(path.stat().st_mtime)
        _set_meta(conn, UNIVERSE_SYNCED_AT_KEY, mtime.isoformat())
    return len(rows)


def export_universe_csv(path: Path) -> int:
    items = load_universe_rows()
    write_stock_csv(path, items)
    return len(items)
