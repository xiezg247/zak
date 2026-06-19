"""雷达预测扫描结果缓存。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from vnpy_ashare.domain.radar.predict import PredictCacheEntry
from vnpy_ashare.domain.time.china import format_china_datetime_minute
from vnpy_ashare.quotes.radar.radar_horizon_stats import HorizonScanStats
from vnpy_ashare.quotes.radar.radar_models import (
    RadarRow,
    radar_row_from_cache_dict,
    radar_row_to_cache_dict,
)
from vnpy_ashare.storage.cache.sqlite_session import sqlite_cache_session
from vnpy_common.paths import get_app_db_path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS radar_predict_cache (
    variant TEXT PRIMARY KEY,
    rows_json TEXT NOT NULL,
    scanned_total INTEGER NOT NULL DEFAULT 0,
    excluded_count INTEGER NOT NULL DEFAULT 0,
    prefilter_total INTEGER NOT NULL DEFAULT 0,
    refined_total INTEGER NOT NULL DEFAULT 0,
    kline_missing INTEGER NOT NULL DEFAULT 0,
    model_label TEXT NOT NULL DEFAULT '',
    computed_at TEXT NOT NULL
);
"""


def _db_path() -> Path:
    return cast(Path, get_app_db_path().parent / "radar_predict_cache.db")


def _connect(db_path: Path | None = None):
    path = db_path or _db_path()
    return sqlite_cache_session(path, _SCHEMA)


def get_predict_cache(variant: str) -> PredictCacheEntry | None:
    text = str(variant or "").strip()
    if not text:
        return None
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM radar_predict_cache WHERE variant = ?",
            (text,),
        ).fetchone()
    if row is None:
        return None
    try:
        payload = json.loads(str(row["rows_json"] or "[]"))
    except (json.JSONDecodeError, TypeError):
        payload = []
    rows = tuple(radar_row_from_cache_dict(item, enrich=False) for item in payload if isinstance(item, dict))
    stats = HorizonScanStats(
        scanned_total=int(row["scanned_total"] or 0),
        excluded_count=int(row["excluded_count"] or 0),
        prefilter_total=int(row["prefilter_total"] or 0),
        refined_total=int(row["refined_total"] or 0),
        kline_missing=int(row["kline_missing"] or 0),
    )
    return PredictCacheEntry(
        variant=text,
        rows=rows,
        stats=stats,
        model_label=str(row["model_label"] or ""),
        computed_at=str(row["computed_at"] or ""),
    )


def get_latest_predict_cache() -> PredictCacheEntry | None:
    for variant in ("predict_baseline",):
        cached = get_predict_cache(variant)
        if cached is not None:
            return cached
    return None


def put_predict_cache(
    *,
    variant: str,
    rows: tuple[RadarRow, ...],
    stats: HorizonScanStats,
    model_label: str,
    computed_at: str | None = None,
) -> None:
    payload = [radar_row_to_cache_dict(row) for row in rows]
    ts = computed_at or format_china_datetime_minute()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO radar_predict_cache (
                variant, rows_json, scanned_total, excluded_count,
                prefilter_total, refined_total, kline_missing, model_label, computed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(variant) DO UPDATE SET
                rows_json = excluded.rows_json,
                scanned_total = excluded.scanned_total,
                excluded_count = excluded.excluded_count,
                prefilter_total = excluded.prefilter_total,
                refined_total = excluded.refined_total,
                kline_missing = excluded.kline_missing,
                model_label = excluded.model_label,
                computed_at = excluded.computed_at
            """,
            (
                variant,
                json.dumps(payload, ensure_ascii=False),
                stats.scanned_total,
                stats.excluded_count,
                stats.prefilter_total,
                stats.refined_total,
                stats.kline_missing,
                model_label,
                ts,
            ),
        )
