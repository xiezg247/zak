"""量比维度：Tushare volume_ratio 与 Redis 行情合并。"""

from __future__ import annotations

from typing import Any

from vnpy_ashare.integrations.tushare.factors import fetch_daily_basic
from vnpy_ashare.screener.data.data_source import load_screening_quote_snapshot
from vnpy_ashare.screener.data.quotes_loader import MarketQuotesLoadError
from vnpy_ashare.screener.data.screening_context import get_volume_ratio_map
from vnpy_ashare.screener.dimensions.base import DimensionHit, quote_hits
from vnpy_ashare.screener.dimensions.scoring import blended_score
from vnpy_ashare.screener.hard_filters import apply_screening_filters
from vnpy_ashare.screener.preset.rules import _quote_row

_VOLUME_RATIO_TIER_2 = 2.0
_VOLUME_RATIO_TIER_5 = 5.0
_VOLUME_RATIO_BONUS_2 = 1.06
_VOLUME_RATIO_BONUS_5 = 1.12


def run_volume_ratio(pool_size: int, *, weight: float) -> tuple[list[DimensionHit], int]:
    try:
        snapshot = load_screening_quote_snapshot()
    except MarketQuotesLoadError:
        return _volume_ratio_from_tushare_only(pool_size, weight=weight)

    ratio_map = _load_volume_ratio_map()
    enriched: list[dict[str, Any]] = []
    for row in snapshot.rows:
        vt_symbol = str(row.get("vt_symbol") or "")
        if not vt_symbol:
            continue
        ratio = ratio_map.get(vt_symbol)
        if ratio is None or ratio <= 0:
            continue
        merged = dict(row)
        merged["volume_ratio"] = ratio
        enriched.append(merged)

    if not enriched:
        return _volume_ratio_from_tushare_only(pool_size, weight=weight)

    enriched = apply_screening_filters(enriched)
    enriched.sort(key=lambda item: float(item.get("volume_ratio") or 0), reverse=True)
    rows: list[dict[str, Any]] = []
    for item in enriched[:pool_size]:
        base = _quote_row(item)
        base["volume_ratio"] = float(item.get("volume_ratio") or 0)
        rows.append(base)

    return quote_hits(
        rows,
        dimension_id="volume_ratio",
        label="量比",
        weight=weight,
        metric_key="volume_ratio",
        reason_builder=lambda row, rank: _volume_ratio_reason(row, rank),
        score_adjustment=lambda row: _volume_ratio_tier_factor(float(row.get("volume_ratio") or 0)),
    ), snapshot.total


def _volume_ratio_tier_factor(ratio: float) -> float:
    if ratio >= _VOLUME_RATIO_TIER_5:
        return _VOLUME_RATIO_BONUS_5
    if ratio >= _VOLUME_RATIO_TIER_2:
        return _VOLUME_RATIO_BONUS_2
    return 1.0


def _volume_ratio_reason(row: dict[str, Any], rank: int) -> str:
    ratio = float(row.get("volume_ratio") or 0)
    tier_note = ""
    if ratio >= _VOLUME_RATIO_TIER_5:
        tier_note = "（强放量）"
    elif ratio >= _VOLUME_RATIO_TIER_2:
        tier_note = "（放量）"
    return f"量比：{ratio:.2f}{tier_note}，排名第 {rank}"


def _load_volume_ratio_map() -> dict[str, float]:
    return get_volume_ratio_map()


def _volume_ratio_from_tushare_only(
    pool_size: int,
    *,
    weight: float,
) -> tuple[list[DimensionHit], int]:
    try:
        basic_rows, _ = fetch_daily_basic()
    except Exception:
        return [], 0
    if not basic_rows:
        return [], 0
    filtered_rows = apply_screening_filters(
        [row for row in basic_rows if float(row.get("volume_ratio") or 0) > 0],
    )
    sorted_rows = sorted(
        filtered_rows,
        key=lambda item: float(item.get("volume_ratio") or 0),
        reverse=True,
    )[:pool_size]
    hits: list[DimensionHit] = []
    for index, row in enumerate(sorted_rows, start=1):
        vt_symbol = str(row.get("vt_symbol") or "")
        if not vt_symbol:
            continue
        ratio = float(row.get("volume_ratio") or 0)
        base = blended_score(index, len(sorted_rows), ratio, [float(r.get("volume_ratio") or 0) for r in sorted_rows])
        hits.append(
            DimensionHit(
                vt_symbol=vt_symbol,
                dimension_id="volume_ratio",
                label="量比",
                weight=weight,
                score=round(base * _volume_ratio_tier_factor(ratio), 1),
                reason=_volume_ratio_reason({"volume_ratio": ratio}, index),
                row={
                    "symbol": row.get("symbol", ""),
                    "name": row.get("name", ""),
                    "vt_symbol": vt_symbol,
                    "close": row.get("close", 0),
                    "volume_ratio": ratio,
                    "turnover_rate": row.get("turnover_rate", 0),
                    "source": "tushare",
                },
            )
        )
    return hits, len(basic_rows)
