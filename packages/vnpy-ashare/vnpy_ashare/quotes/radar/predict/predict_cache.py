"""雷达预测扫描结果缓存。"""

from __future__ import annotations

import json

from vnpy_ashare.domain.radar.predict import PredictCacheEntry
from vnpy_ashare.domain.time.china import format_china_datetime_minute
from vnpy_ashare.quotes.radar.radar_horizon_stats import HorizonScanStats
from vnpy_ashare.quotes.radar.radar_models import (
    RadarRow,
    radar_row_from_cache_dict,
    radar_row_to_cache_dict,
)
from vnpy_ashare.storage.repositories.cache_stores import _radar_predict_repo


def get_predict_cache(variant: str) -> PredictCacheEntry | None:
    text = str(variant or "").strip()
    if not text:
        return None
    row = _radar_predict_repo.get_row(text)
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
    _radar_predict_repo.upsert(
        variant=variant,
        rows_json=json.dumps(payload, ensure_ascii=False),
        scanned_total=stats.scanned_total,
        excluded_count=stats.excluded_count,
        prefilter_total=stats.prefilter_total,
        refined_total=stats.refined_total,
        kline_missing=stats.kline_missing,
        model_label=model_label,
        computed_at=ts,
    )
