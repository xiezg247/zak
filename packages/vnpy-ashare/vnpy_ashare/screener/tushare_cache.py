"""Tushare 因子本地缓存（app_db SQLite）。"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Any

from vnpy_ashare.storage.app_db import init_app_db
from vnpy_common.paths import get_app_db_path

DATASET_DAILY_BASIC = "daily_basic"
DATASET_MONEYFLOW = "moneyflow"
DATASET_DAILY_PCT = "daily_pct"
DATASET_STOCK_INDUSTRY = "stock_industry"

DEFAULT_MAX_AGE = timedelta(hours=24)
INDUSTRY_MAX_AGE = timedelta(days=7)


@contextmanager
def _connect():
    init_app_db()
    path = get_app_db_path()
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


def _parse_fetched_at(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def is_cache_fresh(fetched_at: str, *, max_age: timedelta = DEFAULT_MAX_AGE) -> bool:
    parsed = _parse_fetched_at(fetched_at)
    if parsed is None:
        return False
    return datetime.now() - parsed <= max_age


def get_cached_rows(dataset: str, trade_date: str = "", *, max_age: timedelta = DEFAULT_MAX_AGE) -> list[dict[str, Any]] | None:
    """读取缓存的行列表；过期或不存在时返回 None。"""
    with _connect() as conn:
        row = conn.execute(
            "SELECT fetched_at, payload FROM tushare_factor_cache WHERE dataset = ? AND trade_date = ?",
            (dataset, trade_date),
        ).fetchone()
    if row is None:
        return None
    if not is_cache_fresh(str(row["fetched_at"]), max_age=max_age):
        return None
    payload = json.loads(str(row["payload"]))
    if not isinstance(payload, list):
        return None
    return payload


def set_cached_rows(dataset: str, trade_date: str, rows: list[dict[str, Any]]) -> None:
    fetched_at = datetime.now().isoformat(timespec="seconds")
    payload = json.dumps(rows, ensure_ascii=False)
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO tushare_factor_cache(dataset, trade_date, fetched_at, payload)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(dataset, trade_date) DO UPDATE SET
                fetched_at = excluded.fetched_at,
                payload = excluded.payload
            """,
            (dataset, trade_date, fetched_at, payload),
        )


def get_cached_pct_map(trade_date: str, *, max_age: timedelta = DEFAULT_MAX_AGE) -> dict[str, float] | None:
    rows = get_cached_rows(DATASET_DAILY_PCT, trade_date, max_age=max_age)
    if rows is None:
        return None
    result: dict[str, float] = {}
    for item in rows:
        if not isinstance(item, dict):
            continue
        ts_code = str(item.get("ts_code", "")).strip()
        if not ts_code:
            continue
        try:
            result[ts_code] = float(item.get("pct_chg", 0) or 0)
        except (TypeError, ValueError):
            result[ts_code] = 0.0
    return result


def set_cached_pct_map(trade_date: str, pct_map: dict[str, float]) -> None:
    rows = [{"ts_code": ts_code, "pct_chg": value} for ts_code, value in pct_map.items()]
    set_cached_rows(DATASET_DAILY_PCT, trade_date, rows)


def get_cached_industry_map(*, max_age: timedelta = INDUSTRY_MAX_AGE) -> dict[str, str] | None:
    rows = get_cached_rows(DATASET_STOCK_INDUSTRY, "", max_age=max_age)
    if rows is None:
        return None
    result: dict[str, str] = {}
    for item in rows:
        if not isinstance(item, dict):
            continue
        ts_code = str(item.get("ts_code", "")).strip()
        industry = str(item.get("industry", "") or "").strip()
        if ts_code and industry:
            result[ts_code] = industry
    return result


def set_cached_industry_map(mapping: dict[str, str]) -> None:
    rows = [{"ts_code": ts_code, "industry": industry} for ts_code, industry in mapping.items()]
    set_cached_rows(DATASET_STOCK_INDUSTRY, "", rows)


def clear_tushare_cache() -> None:
    """测试或强制刷新时清空因子缓存。"""
    with _connect() as conn:
        conn.execute("DELETE FROM tushare_factor_cache")
