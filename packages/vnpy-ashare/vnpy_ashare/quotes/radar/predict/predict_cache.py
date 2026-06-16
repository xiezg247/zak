"""雷达预测扫描结果缓存。"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, cast

from vnpy_ashare.quotes.radar.radar_horizon_scan import HorizonScanStats
from vnpy_ashare.quotes.radar.radar_models import RadarRow, enrich_radar_row, float_or_none, quotes_for_vt_symbols
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


@contextmanager
def _connect():
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(_SCHEMA)
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@dataclass(frozen=True)
class PredictCacheEntry:
    variant: str
    rows: tuple[RadarRow, ...]
    stats: HorizonScanStats
    model_label: str
    computed_at: str


def _row_to_dict(row: RadarRow) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "vt_symbol": row.vt_symbol,
        "name": row.name,
        "symbol": row.symbol,
        "metric_label": row.metric_label,
        "metric_value": row.metric_value,
        "sub_label": row.sub_label,
        "sub_value": row.sub_value,
    }
    if row.price is not None:
        payload["last_close"] = row.price
    if row.change_pct is not None:
        payload["change_pct"] = row.change_pct
    return payload


def _row_from_dict(raw: dict[str, Any], *, quote: dict[str, Any] | None = None) -> RadarRow:
    vt_symbol = str(raw.get("vt_symbol") or "").strip()
    base = quote if quote is not None else {"vt_symbol": vt_symbol}
    row = RadarRow(
        vt_symbol=vt_symbol,
        name=str(raw.get("name") or ""),
        symbol=str(raw.get("symbol") or ""),
        price=float_or_none(raw.get("last_close")),
        change_pct=float_or_none(raw.get("change_pct")),
        metric_label=str(raw.get("metric_label") or ""),
        metric_value=str(raw.get("metric_value") or ""),
        sub_label=str(raw.get("sub_label") or ""),
        sub_value=str(raw.get("sub_value") or ""),
    )
    return enrich_radar_row(row, base)


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
    vt_symbols = [str(item.get("vt_symbol") or "").strip() for item in payload if isinstance(item, dict)]
    vt_symbols = [vt for vt in vt_symbols if vt]
    quotes = quotes_for_vt_symbols(vt_symbols)
    rows = tuple(
        _row_from_dict(item, quote=quotes.get(str(item.get("vt_symbol") or "").strip(), {}))
        for item in payload
        if isinstance(item, dict)
    )
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
    for variant in ("predict_lgb", "predict_baseline"):
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
    payload = [_row_to_dict(row) for row in rows]
    ts = computed_at or datetime.now().strftime("%Y-%m-%d %H:%M")
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
