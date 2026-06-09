"""Tushare Pro 交易日历：拉取并缓存到本地 SQLite。"""

from __future__ import annotations

import os
import threading
from datetime import date, datetime, timedelta

from vnpy_ashare.app_db import get_meta, init_app_db, set_meta
from vnpy_ashare.paths import APP_DB_PATH

TRADE_CAL_SYNCED_AT_KEY = "trade_calendar_synced_at"
TRADE_CAL_RANGE_START_KEY = "trade_calendar_range_start"
TRADE_CAL_RANGE_END_KEY = "trade_calendar_range_end"
CACHE_MAX_AGE = timedelta(days=7)
DEFAULT_CAL_START = date(2019, 1, 1)

_sync_lock = threading.Lock()


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def _format_date(value: date) -> str:
    return value.isoformat()


def _default_cal_end(today: date | None = None) -> date:
    current = today or date.today()
    return date(current.year + 1, 12, 31)


def _get_tushare_pro():
    from dotenv import load_dotenv

    from vnpy_ashare.paths import ENV_FILE

    load_dotenv(ENV_FILE)
    token = os.getenv("TUSHARE_TOKEN") or os.getenv("TS_TOKEN")
    if not token:
        try:
            from vnpy.trader.setting import SETTINGS

            token = SETTINGS.get("datafeed.password") or ""
        except Exception:
            token = ""
    if not token:
        return None
    import tushare as ts

    ts.set_token(token)
    return ts.pro_api(token)


def _fetch_trade_calendar(start: date, end: date) -> list[tuple[str, int]]:
    pro = _get_tushare_pro()
    if pro is None:
        return []

    frame = pro.trade_cal(
        exchange="SSE",
        start_date=start.strftime("%Y%m%d"),
        end_date=end.strftime("%Y%m%d"),
    )
    if frame is None or frame.empty:
        return []

    rows: list[tuple[str, int]] = []
    for _, row in frame.iterrows():
        cal_date = str(row["cal_date"])
        if len(cal_date) == 8:
            cal_date = f"{cal_date[:4]}-{cal_date[4:6]}-{cal_date[6:8]}"
        is_open = 1 if str(row["is_open"]) == "1" else 0
        rows.append((cal_date, is_open))
    return rows


def _upsert_rows(rows: list[tuple[str, int]]) -> None:
    if not rows:
        return
    import sqlite3

    init_app_db()
    with sqlite3.connect(APP_DB_PATH) as conn:
        conn.executemany(
            "INSERT INTO trade_calendar(cal_date, is_open) VALUES (?, ?) ON CONFLICT(cal_date) DO UPDATE SET is_open = excluded.is_open",
            rows,
        )
        conn.commit()


def _cached_range() -> tuple[date | None, date | None]:
    start_raw = get_meta(TRADE_CAL_RANGE_START_KEY)
    end_raw = get_meta(TRADE_CAL_RANGE_END_KEY)
    start = _parse_date(start_raw) if start_raw else None
    end = _parse_date(end_raw) if end_raw else None
    return start, end


def _cache_is_fresh() -> bool:
    synced_at_raw = get_meta(TRADE_CAL_SYNCED_AT_KEY)
    if not synced_at_raw:
        return False
    synced_at = datetime.fromisoformat(synced_at_raw)
    return datetime.now() - synced_at < CACHE_MAX_AGE


def _range_covers(start: date, end: date, day: date) -> bool:
    return start <= day <= end


def sync_trade_calendar(start: date, end: date) -> int:
    """从 Tushare Pro 同步 [start, end] 日历，返回写入条数。"""
    if start > end:
        return 0

    rows = _fetch_trade_calendar(start, end)
    if not rows:
        return 0

    _upsert_rows(rows)
    cached_start, cached_end = _cached_range()
    new_start = start if cached_start is None else min(cached_start, start)
    new_end = end if cached_end is None else max(cached_end, end)
    set_meta(TRADE_CAL_RANGE_START_KEY, _format_date(new_start))
    set_meta(TRADE_CAL_RANGE_END_KEY, _format_date(new_end))
    set_meta(TRADE_CAL_SYNCED_AT_KEY, datetime.now().isoformat())
    return len(rows)


def ensure_calendar_covers(day: date) -> bool:
    """确保本地缓存覆盖 day；成功同步返回 True。"""
    with _sync_lock:
        cached_start, cached_end = _cached_range()
        needs_sync = cached_start is None or cached_end is None or not _range_covers(cached_start, cached_end, day) or not _cache_is_fresh()
        if not needs_sync:
            return lookup_trading_day(day) is not None

        start = min(DEFAULT_CAL_START, day)
        end = max(_default_cal_end(day), day)
        count = sync_trade_calendar(start, end)
        return count > 0


def lookup_trading_day(day: date) -> bool | None:
    """查询缓存；未命中返回 None。"""
    import sqlite3

    init_app_db()
    with sqlite3.connect(APP_DB_PATH) as conn:
        row = conn.execute(
            "SELECT is_open FROM trade_calendar WHERE cal_date = ?",
            (_format_date(day),),
        ).fetchone()
    if row is None:
        return None
    return bool(row[0])


def clear_trade_calendar_cache() -> None:
    """测试用：清空交易日历缓存。"""
    import sqlite3

    init_app_db()
    with sqlite3.connect(APP_DB_PATH) as conn:
        conn.execute("DELETE FROM trade_calendar")
        conn.execute(
            "DELETE FROM meta WHERE key IN (?, ?, ?)",
            (
                TRADE_CAL_SYNCED_AT_KEY,
                TRADE_CAL_RANGE_START_KEY,
                TRADE_CAL_RANGE_END_KEY,
            ),
        )
        conn.commit()
