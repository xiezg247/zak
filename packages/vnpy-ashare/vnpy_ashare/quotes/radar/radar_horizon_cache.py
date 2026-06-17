"""雷达页未来展望扫描结果缓存（全市场 Top N）。"""

from __future__ import annotations

from pydantic import Field

from vnpy_ashare.domain.base import FrozenModel, MutableModel

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import cast

from vnpy_ashare.domain.time.china import format_china_datetime_minute
from vnpy_ashare.quotes.radar.radar_models import (
    RadarRow,
    quotes_for_vt_symbols,
    radar_row_from_cache_dict,
    radar_row_to_cache_dict,
)
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


class HorizonCacheEntry(FrozenModel):
    variant: str = Field(description="变体标识")
    rows: tuple[RadarRow, ...] = Field(description="数据行列表")
    scanned_total: int = Field(description="全市场扫描总数")
    excluded_count: int = Field(description="排除标的数")
    prefilter_total: int = Field(description="粗筛池数量")
    refined_total: int = Field(description="精算数量")
    kline_missing: int = Field(description="日 K 缺失数量")
    strategy_key: str = Field(description="策略配置键")
    computed_at: str = Field(description="计算时间")


def get_horizon_cache(variant: str) -> HorizonCacheEntry | None:
    text = str(variant or "").strip()
    if not text:
        return None
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM radar_horizon_cache WHERE variant = ?",
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
        radar_row_from_cache_dict(item, quote=quotes.get(str(item.get("vt_symbol") or "").strip(), {}))
        for item in payload
        if isinstance(item, dict)
    )
    return HorizonCacheEntry(
        variant=text,
        rows=rows,
        scanned_total=int(row["scanned_total"] or 0),
        excluded_count=int(row["excluded_count"] or 0),
        prefilter_total=int(row["prefilter_total"] or 0),
        refined_total=int(row["refined_total"] or 0),
        kline_missing=int(row["kline_missing"] or 0),
        strategy_key=str(row["strategy_key"] or ""),
        computed_at=str(row["computed_at"] or ""),
    )


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
                text,
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
