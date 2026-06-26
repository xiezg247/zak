"""盘中定时选股快照复用（发现类卡片跳过全市场扫描）。"""

from __future__ import annotations

from datetime import datetime

from vnpy_ashare.domain.screener.dimension_hit import DimensionHit, dimension_hit_row
from vnpy_ashare.domain.screener.result_row import ScreenerResultRow
from vnpy_ashare.domain.time.china import CHINA_TZ, DATETIME_FMT, DATETIME_MINUTE_FMT, china_now
from vnpy_ashare.quotes.radar.loaders.screener import find_run_for_task_variant
from vnpy_ashare.screener.run.run_store import ScreenerRunRecord

_INTRADAY_RUN_MAX_AGE_SEC = 600.0
_VOLUME_DIMENSION_IDS = ("volume_surge", "volume_ratio")


def _parse_created_at(created_at: str) -> datetime | None:
    text = str(created_at or "").strip()
    for fmt in (DATETIME_FMT, DATETIME_MINUTE_FMT):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=CHINA_TZ)
        except ValueError:
            continue
    return None


def run_age_sec(record: ScreenerRunRecord) -> float | None:
    created = _parse_created_at(record.created_at)
    if created is None:
        return None
    return max(0.0, (china_now() - created).total_seconds())


def peek_fresh_intraday_screen_run(*, max_age_sec: float = _INTRADAY_RUN_MAX_AGE_SEC) -> ScreenerRunRecord | None:
    """读取仍在有效期内的 ``screen_intraday`` 落库结果。"""
    record = find_run_for_task_variant("scheduled_intraday")
    if record is None or not record.rows:
        return None
    age = run_age_sec(record)
    if age is None or age > max_age_sec:
        return None
    return record


def volume_hits_from_intraday_run(
    record: ScreenerRunRecord,
    pool_size: int,
) -> tuple[list[DimensionHit], int]:
    """从盘中多因子结果提取放量 / 量比维度命中。"""
    ranked: list[tuple[float, ScreenerResultRow, str]] = []
    for row in record.rows:
        dims = row.get("dimensions")
        if not isinstance(dims, dict):
            continue
        dim_id = next((key for key in _VOLUME_DIMENSION_IDS if key in dims), None)
        if dim_id is None:
            continue
        try:
            score = float(dims[dim_id])
        except (TypeError, ValueError):
            continue
        ranked.append((score, row, dim_id))
    ranked.sort(key=lambda item: item[0], reverse=True)

    hits: list[DimensionHit] = []
    for score, row, dim_id in ranked[:pool_size]:
        payload = row.to_dict()
        vt_symbol = str(payload.get("vt_symbol") or "").strip()
        if not vt_symbol:
            continue
        label = "放量" if dim_id == "volume_surge" else "量比"
        hits.append(
            DimensionHit(
                vt_symbol=vt_symbol,
                dimension_id=dim_id,
                label=label,
                weight=1.0,
                score=score,
                reason=str(payload.get("hit_reason") or f"{label} {score:.1f}"),
                row=dimension_hit_row(payload),
            )
        )
    return hits, record.total_scanned
