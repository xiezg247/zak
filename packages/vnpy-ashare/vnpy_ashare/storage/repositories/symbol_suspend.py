"""标的停牌日 repository。"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from vnpy.trader.constant import Exchange

from vnpy_ashare.domain.calendar import last_trading_day, load_open_trading_days
from vnpy_ashare.integrations.tushare.suspend import fetch_suspend_d
from vnpy_ashare.storage.connection import connect, set_meta

SUSPEND_SYNCED_AT_KEY = "symbol_suspend_synced_at"
SUSPEND_LAST_TRADE_DATE_KEY = "symbol_suspend_last_trade_date"
DEFAULT_LOOKBACK_DAYS = 3


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def _format_date(value: date) -> str:
    return value.isoformat()


def _upsert_rows(rows: list[tuple[str, str, str, str]]) -> int:
    if not rows:
        return 0
    with connect() as conn:
        conn.executemany(
            """
            INSERT INTO symbol_suspend_days(symbol, exchange, cal_date, suspend_type)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(symbol, exchange, cal_date) DO UPDATE SET
                suspend_type = excluded.suspend_type
            """,
            rows,
        )
    return len(rows)


def sync_suspend_for_date(trade_date: date) -> int:
    """同步单个交易日的停牌记录，返回写入条数。"""
    rows = fetch_suspend_d(trade_date)
    payload = [(row["symbol"], row["exchange"], row["cal_date"], row["suspend_type"]) for row in rows]
    count = _upsert_rows(payload)
    set_meta(SUSPEND_LAST_TRADE_DATE_KEY, _format_date(trade_date))
    set_meta(SUSPEND_SYNCED_AT_KEY, datetime.now().isoformat())
    return count


def sync_suspend_recent(*, lookback_days: int = DEFAULT_LOOKBACK_DAYS, end: date | None = None) -> tuple[int, list[date]]:
    """同步最近若干 A 股交易日的停牌记录（增量幂等）。"""
    latest = end or last_trading_day()
    start = latest - timedelta(days=max(lookback_days * 2, 14))
    trading_days = load_open_trading_days(start, latest)
    if not trading_days:
        return 0, []
    recent = trading_days[-lookback_days:]
    total = 0
    for day in recent:
        total += sync_suspend_for_date(day)
    return total, recent


def load_suspend_days(
    symbol: str,
    exchange: Exchange | str,
    start: date,
    end: date,
) -> set[date]:
    """读取 [start, end] 内已知停牌日。"""
    if start > end:
        return set()
    exchange_value = exchange.value if isinstance(exchange, Exchange) else str(exchange)
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT cal_date FROM symbol_suspend_days
            WHERE symbol = ? AND exchange = ? AND cal_date >= ? AND cal_date <= ?
            """,
            (symbol, exchange_value, _format_date(start), _format_date(end)),
        ).fetchall()
    return {_parse_date(str(row[0])) for row in rows}


def load_suspended_keys(trade_date: date) -> frozenset[tuple[str, str]]:
    """指定交易日全市场停牌标的 (symbol, exchange)。"""
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT symbol, exchange FROM symbol_suspend_days
            WHERE cal_date = ?
            """,
            (_format_date(trade_date),),
        ).fetchall()
    return frozenset((str(row[0]), str(row[1])) for row in rows)


def ensure_suspend_keys_for_screening(*, trade_date: date | None = None) -> frozenset[tuple[str, str]]:
    """选股硬过滤用：读取当日停牌列表，本地无缓存时尝试增量同步一次。"""
    day = trade_date or last_trading_day()
    keys = load_suspended_keys(day)
    if keys:
        return keys
    try:
        sync_suspend_for_date(day)
    except Exception:
        return frozenset()
    return load_suspended_keys(day)


def clear_symbol_suspend_cache() -> None:
    """测试用：清空停牌日缓存。"""
    with connect() as conn:
        conn.execute("DELETE FROM symbol_suspend_days")
        conn.execute(
            "DELETE FROM meta WHERE key IN (?, ?)",
            (SUSPEND_SYNCED_AT_KEY, SUSPEND_LAST_TRADE_DATE_KEY),
        )
