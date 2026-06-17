"""zak.db 连接、Schema 与 meta 键值。"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

from vnpy_common.paths import get_app_db_path

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

CREATE TABLE IF NOT EXISTS watchlist_groups (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    position_cap_pct REAL
);

CREATE TABLE IF NOT EXISTS watchlist_group_members (
    group_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    exchange TEXT NOT NULL,
    PRIMARY KEY (group_id, symbol, exchange),
    FOREIGN KEY (group_id) REFERENCES watchlist_groups(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_watchlist_group_members_symbol
    ON watchlist_group_members(symbol, exchange);

CREATE TABLE IF NOT EXISTS watchlist_positions (
    symbol TEXT NOT NULL,
    exchange TEXT NOT NULL,
    cost_price REAL NOT NULL,
    volume INTEGER NOT NULL,
    buy_date TEXT NOT NULL,
    notes TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT 'manual',
    plan_pct REAL,
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

CREATE TABLE IF NOT EXISTS symbol_suspend_days (
    symbol TEXT NOT NULL,
    exchange TEXT NOT NULL,
    cal_date TEXT NOT NULL,
    suspend_type TEXT NOT NULL DEFAULT 'S',
    PRIMARY KEY (symbol, exchange, cal_date)
);

CREATE INDEX IF NOT EXISTS idx_symbol_suspend_lookup
    ON symbol_suspend_days(symbol, exchange, cal_date);

CREATE TABLE IF NOT EXISTS stock_note_memos (
    symbol TEXT NOT NULL,
    exchange TEXT NOT NULL,
    body TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL,
    PRIMARY KEY (symbol, exchange)
);

CREATE TABLE IF NOT EXISTS stock_note_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    exchange TEXT NOT NULL,
    body TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_stock_note_entries_lookup
    ON stock_note_entries (symbol, exchange, created_at DESC);

CREATE TABLE IF NOT EXISTS stock_analysis_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    exchange TEXT NOT NULL,
    title TEXT NOT NULL DEFAULT '',
    body TEXT NOT NULL,
    source_scope TEXT NOT NULL DEFAULT '',
    context_json TEXT NOT NULL DEFAULT '',
    summary TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_stock_analysis_reports_lookup
    ON stock_analysis_reports (symbol, exchange, created_at DESC);

CREATE TABLE IF NOT EXISTS sector_flow_daily (
    trade_date TEXT NOT NULL,
    sector_kind TEXT NOT NULL,
    sector_id TEXT NOT NULL,
    name TEXT NOT NULL,
    change_pct REAL NOT NULL,
    net_flow_yi REAL NOT NULL,
    flow_source TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (trade_date, sector_kind, sector_id)
);

CREATE INDEX IF NOT EXISTS idx_sector_flow_daily_lookup
    ON sector_flow_daily(sector_kind, sector_id, trade_date DESC);

CREATE TABLE IF NOT EXISTS notify_delivery_log (
    id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    channel TEXT NOT NULL DEFAULT 'feishu',
    payload_json TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL,
    error TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_notify_delivery_log_created
    ON notify_delivery_log(created_at DESC);

CREATE TABLE IF NOT EXISTS trading_plans (
    id TEXT PRIMARY KEY,
    trade_date TEXT NOT NULL,
    emotion_expected TEXT NOT NULL DEFAULT '',
    max_position_pct REAL NOT NULL DEFAULT 0,
    notes TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'draft',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_trading_plans_trade_date
    ON trading_plans(trade_date DESC, status);

CREATE TABLE IF NOT EXISTS trading_plan_symbols (
    plan_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    exchange TEXT NOT NULL,
    allowed_modes TEXT NOT NULL DEFAULT '',
    entry_conditions TEXT NOT NULL DEFAULT '',
    exit_conditions TEXT NOT NULL DEFAULT '',
    sort_order INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (plan_id, symbol, exchange),
    FOREIGN KEY (plan_id) REFERENCES trading_plans(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS trade_journal (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    exchange TEXT NOT NULL,
    side TEXT NOT NULL,
    trade_date TEXT NOT NULL,
    price REAL NOT NULL,
    volume INTEGER NOT NULL,
    mode TEXT NOT NULL DEFAULT '',
    plan_id TEXT,
    on_plan INTEGER NOT NULL DEFAULT 0,
    violation_tags TEXT NOT NULL DEFAULT '',
    pnl REAL,
    pnl_pct REAL,
    reason TEXT NOT NULL DEFAULT '',
    emotion_stage TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_trade_journal_trade_date
    ON trade_journal(trade_date DESC, created_at DESC);
"""


def _db_path() -> Path:

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


def _ensure_column(
    conn: sqlite3.Connection,
    table: str,
    column: str,
    definition: str,
) -> None:
    columns = {str(row[1]) for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {definition}")


def _migrate_app_db(conn: sqlite3.Connection) -> None:
    _ensure_column(conn, "watchlist_positions", "plan_pct", "plan_pct REAL")
    _ensure_column(conn, "watchlist_groups", "position_cap_pct", "position_cap_pct REAL")


def init_app_db() -> Path:
    """初始化数据库表结构。"""
    with connect() as conn:
        conn.executescript(_SCHEMA)
        _migrate_app_db(conn)
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
