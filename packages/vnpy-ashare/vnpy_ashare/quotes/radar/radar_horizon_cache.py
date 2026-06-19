"""雷达页未来展望扫描结果缓存（全市场 Top N）。"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import cast

from vnpy_ashare.domain.radar.horizon_cache import HorizonCacheEntry
from vnpy_ashare.domain.time.china import format_china_datetime_minute
from vnpy_ashare.quotes.radar.radar_models import (
    RadarRow,
    radar_row_from_cache_dict,
    radar_row_to_cache_dict,
)
from vnpy_ashare.storage.cache.sqlite_session import sqlite_cache_session
from vnpy_common.paths import get_app_db_path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS radar_horizon_cache (
    variant TEXT PRIMARY KEY,
    rows_json TEXT NOT NULL,
    scanned_total INTEGER NOT NULL DEFAULT 0,
    excluded_count INTEGER NOT NULL DEFAULT 0,
    prefilter_total INTEGER NOT NULL DEFAULT 0,
    refined_total INTEGER NOT NULL DEFAULT 0,
    kline_missing INTEGER NOT NULL DEFAULT 0,
    strategy_key TEXT NOT NULL DEFAULT '',
    computed_at TEXT NOT NULL
);
"""


def _db_path() -> Path:
    return cast(Path, get_app_db_path().parent / "radar_horizon_cache.db")


def _connect(db_path: Path | None = None):
    path = db_path or _db_path()
    return sqlite_cache_session(path, _SCHEMA)


def horizon_cache_storage_key(variant: str, strategy_key: str) -> str:
    """缓存主键：变体 + 策略配置键（支持同变体多策略并存）。"""
    text = str(variant or "").strip()
    key = str(strategy_key or "").strip()
    if not text:
        return ""
    if not key:
        return text
    return f"{text}|{key}"


def _entry_from_row(row: sqlite3.Row, *, logical_variant: str) -> HorizonCacheEntry:
    try:
        payload = json.loads(str(row["rows_json"] or "[]"))
    except (json.JSONDecodeError, TypeError):
        payload = []
    rows = tuple(radar_row_from_cache_dict(item, enrich=False) for item in payload if isinstance(item, dict))
    return HorizonCacheEntry(
        variant=logical_variant,
        rows=rows,
        scanned_total=int(row["scanned_total"] or 0),
        excluded_count=int(row["excluded_count"] or 0),
        prefilter_total=int(row["prefilter_total"] or 0),
        refined_total=int(row["refined_total"] or 0),
        kline_missing=int(row["kline_missing"] or 0),
        strategy_key=str(row["strategy_key"] or ""),
        computed_at=str(row["computed_at"] or ""),
    )


def get_horizon_cache(variant: str, *, strategy_key: str = "") -> HorizonCacheEntry | None:
    text = str(variant or "").strip()
    if not text:
        return None
    key = str(strategy_key or "").strip()
    storage_key = horizon_cache_storage_key(text, key) if key else text
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM radar_horizon_cache WHERE variant = ?",
            (storage_key,),
        ).fetchone()
    if row is None:
        return None
    cached_key = str(row["strategy_key"] or "").strip()
    if cached_key != key:
        return None
    return _entry_from_row(row, logical_variant=text)


def put_horizon_cache(
    variant: str,
    rows: tuple[RadarRow, ...],
    *,
    scanned_total: int,
    excluded_count: int,
    prefilter_total: int,
    refined_total: int,
    kline_missing: int,
    strategy_key: str,
    computed_at: str | None = None,
) -> None:
    text = str(variant or "").strip()
    if not text:
        return
    storage_key = horizon_cache_storage_key(text, strategy_key)
    if not storage_key:
        return
    stamp = computed_at or format_china_datetime_minute()
    payload = json.dumps([radar_row_to_cache_dict(row) for row in rows], ensure_ascii=False)
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO radar_horizon_cache (
                variant, rows_json, scanned_total, excluded_count,
                prefilter_total, refined_total, kline_missing,
                strategy_key, computed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(variant) DO UPDATE SET
                rows_json = excluded.rows_json,
                scanned_total = excluded.scanned_total,
                excluded_count = excluded.excluded_count,
                prefilter_total = excluded.prefilter_total,
                refined_total = excluded.refined_total,
                kline_missing = excluded.kline_missing,
                strategy_key = excluded.strategy_key,
                computed_at = excluded.computed_at
            """,
            (
                storage_key,
                payload,
                int(scanned_total),
                int(excluded_count),
                int(prefilter_total),
                int(refined_total),
                int(kline_missing),
                str(strategy_key or ""),
                stamp,
            ),
        )


def build_horizon_subtitle(
    entry: HorizonCacheEntry,
    *,
    signal_recent_days: int,
    strategy_label: str,
) -> str:
    parts = [
        f"全市场 {entry.scanned_total} 只",
        f"排除自选等 {entry.excluded_count}",
        f"精算 {entry.refined_total}",
        f"约 {signal_recent_days} 日窗口",
        f"策略 {strategy_label}",
        "非价格预测",
    ]
    return " · ".join(parts)
