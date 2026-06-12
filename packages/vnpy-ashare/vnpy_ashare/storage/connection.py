"""zak.db 连接、Schema 与 meta 键值。"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

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

CREATE TABLE IF NOT EXISTS watchlist_positions (
    symbol TEXT NOT NULL,
    exchange TEXT NOT NULL,
    cost_price REAL NOT NULL,
    volume INTEGER NOT NULL,
    buy_date TEXT NOT NULL,
    notes TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT 'manual',
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
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

CREATE TABLE IF NOT EXISTS tushare_factor_cache (
    dataset TEXT NOT NULL,
    trade_date TEXT NOT NULL DEFAULT '',
    fetched_at TEXT NOT NULL,
    payload TEXT NOT NULL,
    PRIMARY KEY (dataset, trade_date)
);

CREATE TABLE IF NOT EXISTS financial_reports (
    ts_code TEXT NOT NULL,
    report_type TEXT NOT NULL,
    end_date TEXT NOT NULL,
    ann_date TEXT NOT NULL DEFAULT '',
    period TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT 'tushare',
    fetched_at TEXT NOT NULL,
    payload TEXT NOT NULL,
    PRIMARY KEY (ts_code, report_type, end_date)
);

CREATE INDEX IF NOT EXISTS idx_financial_reports_ts_type
    ON financial_reports(ts_code, report_type, end_date DESC);

CREATE TABLE IF NOT EXISTS financial_snapshots (
    ts_code TEXT NOT NULL,
    end_date TEXT NOT NULL,
    revenue REAL,
    net_income REAL,
    operate_profit REAL,
    basic_eps REAL,
    total_assets REAL,
    total_liab REAL,
    total_equity REAL,
    ocf REAL,
    icf REAL,
    fcf_flow REAL,
    free_cashflow REAL,
    roe REAL,
    gross_margin REAL,
    net_margin REAL,
    debt_ratio REAL,
    current_ratio REAL,
    revenue_yoy REAL,
    net_income_yoy REAL,
    roe_yoy REAL,
    ocf_to_profit REAL,
    computed_at TEXT NOT NULL,
    PRIMARY KEY (ts_code, end_date)
);

CREATE TABLE IF NOT EXISTS financial_sync_meta (
    ts_code TEXT PRIMARY KEY,
    last_sync_at TEXT NOT NULL,
    latest_end_date TEXT NOT NULL DEFAULT '',
    latest_ann_date TEXT NOT NULL DEFAULT '',
    sync_status TEXT NOT NULL DEFAULT 'ok',
    error_message TEXT NOT NULL DEFAULT '',
    periods_count INTEGER NOT NULL DEFAULT 0,
    last_access_at TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS valuation_history (
    ts_code TEXT NOT NULL,
    trade_date TEXT NOT NULL,
    close REAL,
    pe_ttm REAL,
    pb REAL,
    total_mv REAL,
    circ_mv REAL,
    turnover_rate REAL,
    fetched_at TEXT NOT NULL,
    PRIMARY KEY (ts_code, trade_date)
);

CREATE INDEX IF NOT EXISTS idx_valuation_history_ts_date
    ON valuation_history(ts_code, trade_date DESC);

CREATE TABLE IF NOT EXISTS disclosure_calendar (
    ts_code TEXT NOT NULL,
    end_date TEXT NOT NULL,
    pre_date TEXT NOT NULL DEFAULT '',
    ann_date TEXT NOT NULL DEFAULT '',
    actual_date TEXT NOT NULL DEFAULT '',
    fetched_at TEXT NOT NULL,
    PRIMARY KEY (ts_code, end_date)
);
"""


def _db_path() -> Path:
    from vnpy_common.paths import get_app_db_path

    return get_app_db_path()


@contextmanager
def connect():
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
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
    with connect() as conn:
        conn.executescript(_SCHEMA)
    return _db_path()


def _set_meta(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO meta(key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )


def _get_meta(conn: sqlite3.Connection, key: str) -> str | None:
    row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None


def get_meta(key: str) -> str | None:
    init_app_db()
    with connect() as conn:
        return _get_meta(conn, key)


def set_meta(key: str, value: str) -> None:
    init_app_db()
    with connect() as conn:
        _set_meta(conn, key, value)
