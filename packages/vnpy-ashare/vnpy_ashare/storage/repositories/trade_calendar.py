"""Tushare Pro 交易日历 repository。"""

from __future__ import annotations

import os
import threading
from datetime import date, datetime, timedelta

import tushare as ts
from dotenv import load_dotenv
from sqlalchemy import delete, select
from vnpy.trader.setting import SETTINGS

from vnpy_ashare.storage.repository.app import AppBaseRepository, MetaRepository
from vnpy_common.paths import ENV_FILE
from vnpy_common.storage.repository import bulk_upsert
from vnpy_common.storage.tables import trade_calendar as tc

TRADE_CAL_SYNCED_AT_KEY = "trade_calendar_synced_at"
TRADE_CAL_RANGE_START_KEY = "trade_calendar_range_start"
TRADE_CAL_RANGE_END_KEY = "trade_calendar_range_end"
CACHE_MAX_AGE = timedelta(days=7)
DEFAULT_CAL_START = date(2019, 1, 1)

_sync_lock = threading.Lock()
_meta = MetaRepository()


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def _format_date(value: date) -> str:
    return value.isoformat()


def _default_cal_end(today: date | None = None) -> date:
    current = today or date.today()
    return date(current.year + 1, 12, 31)


def _get_tushare_pro():

    load_dotenv(ENV_FILE)
    token = os.getenv("TUSHARE_TOKEN") or os.getenv("TS_TOKEN")
    if not token:
        try:
            token = SETTINGS.get("datafeed.password") or ""
        except Exception:
            token = ""
    if not token:
        return None

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


class TradeCalendarRepository(AppBaseRepository):
    table = tc

    def upsert_rows(self, rows: list[tuple[str, int]]) -> None:
        if not rows:
            return
        values = [{"cal_date": cal_date, "is_open": is_open} for cal_date, is_open in rows]

        def _write(conn) -> None:
            bulk_upsert(
                conn,
                self.table,
                values,
                conflict_columns=("cal_date",),
                update_columns=("is_open",),
            )

        self.run(_write)

    def cached_range(self) -> tuple[date | None, date | None]:
        start_raw = _meta.get_value(TRADE_CAL_RANGE_START_KEY)
        end_raw = _meta.get_value(TRADE_CAL_RANGE_END_KEY)
        start = _parse_date(start_raw) if start_raw else None
        end = _parse_date(end_raw) if end_raw else None
        return start, end

    def cache_is_fresh(self) -> bool:
        synced_at_raw = _meta.get_value(TRADE_CAL_SYNCED_AT_KEY)
        if not synced_at_raw:
            return False
        synced_at = datetime.fromisoformat(synced_at_raw)
        return datetime.now() - synced_at < CACHE_MAX_AGE

    def lookup(self, day: date) -> bool | None:
        row = self.fetchone(select(tc.c.is_open).where(tc.c.cal_date == _format_date(day)))
        if row is None:
            return None
        return bool(row[0])

    def load_open_days(self, start: date, end: date) -> list[date]:
        rows = self.fetchall(
            select(tc.c.cal_date)
            .where(
                tc.c.cal_date >= _format_date(start),
                tc.c.cal_date <= _format_date(end),
                tc.c.is_open == 1,
            )
            .order_by(tc.c.cal_date)
        )
        return [_parse_date(str(row[0])) for row in rows]

    def clear_cache(self) -> None:
        def _write(conn) -> None:
            conn.execute_stmt(delete(tc))

        self.run(_write)
        _meta.delete_keys(
            TRADE_CAL_SYNCED_AT_KEY,
            TRADE_CAL_RANGE_START_KEY,
            TRADE_CAL_RANGE_END_KEY,
        )


_repo = TradeCalendarRepository()


def _range_covers(start: date, end: date, day: date) -> bool:
    return start <= day <= end


def sync_trade_calendar(start: date, end: date) -> int:
    """从 Tushare Pro 同步 [start, end] 日历，返回写入条数。"""
    if start > end:
        return 0

    rows = _fetch_trade_calendar(start, end)
    if not rows:
        return 0

    _repo.upsert_rows(rows)
    cached_start, cached_end = _repo.cached_range()
    new_start = start if cached_start is None else min(cached_start, start)
    new_end = end if cached_end is None else max(cached_end, end)
    _meta.upsert_value(TRADE_CAL_RANGE_START_KEY, _format_date(new_start))
    _meta.upsert_value(TRADE_CAL_RANGE_END_KEY, _format_date(new_end))
    _meta.upsert_value(TRADE_CAL_SYNCED_AT_KEY, datetime.now().isoformat())
    return len(rows)


def ensure_calendar_covers(day: date) -> bool:
    """确保本地缓存覆盖 day；成功同步返回 True。"""
    with _sync_lock:
        cached_start, cached_end = _repo.cached_range()
        needs_sync = (
            cached_start is None
            or cached_end is None
            or not _range_covers(cached_start, cached_end, day)
            or not _repo.cache_is_fresh()
        )
        if not needs_sync:
            return lookup_trading_day(day) is not None

        start = min(DEFAULT_CAL_START, day)
        end = max(_default_cal_end(day), day)
        count = sync_trade_calendar(start, end)
        return count > 0


def load_open_trading_days(start: date, end: date) -> list[date]:
    """一次性读取 [start, end] 内开市日（升序）；无缓存时降级为周一至周五。"""
    if start > end:
        return []

    ensure_calendar_covers(start)
    ensure_calendar_covers(end)

    rows = _repo.load_open_days(start, end)
    if rows:
        return rows

    days: list[date] = []
    current = start
    while current <= end:
        if current.weekday() < 5:
            days.append(current)
        current += timedelta(days=1)
    return days


def lookup_trading_day(day: date) -> bool | None:
    """查询缓存；未命中返回 None。"""
    return _repo.lookup(day)


def previous_open_trading_day(day: date, *, max_lookback: int = 15) -> date | None:
    """返回 day 之前最近一个开市日；无日历缓存时降级为跳过周末。"""
    current = day - timedelta(days=1)
    for _ in range(max_lookback):
        if current.weekday() >= 5:
            current -= timedelta(days=1)
            continue
        flag = lookup_trading_day(current)
        if flag is True:
            return current
        if flag is None and current.weekday() < 5:
            return current
        current -= timedelta(days=1)
    return None


def clear_trade_calendar_cache() -> None:
    """测试用：清空交易日历缓存。"""
    _repo.clear_cache()
