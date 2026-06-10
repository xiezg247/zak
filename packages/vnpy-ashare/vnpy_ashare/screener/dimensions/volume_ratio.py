"""量比维度：Tushare volume_ratio 与 Redis 行情合并。"""

from __future__ import annotations

from typing import Any

from vnpy_ashare.screener.data_source import load_screening_quote_snapshot
from vnpy_ashare.screener.dimensions.base import DimensionHit, quote_hits, rank_score
from vnpy_ashare.screener.factors import fetch_daily_basic
from vnpy_ashare.screener.quotes_loader import MarketQuotesLoadError
from vnpy_ashare.screener.rules import _quote_row


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
        merged = dict(row)
        ratio = ratio_map.get(vt_symbol)
        if ratio is not None and ratio > 0:
            merged["volume_ratio"] = ratio
        elif float(row.get("volume") or 0) > 0:
            merged["volume_ratio"] = float(row.get("volume") or 0)
        else:
            continue
        enriched.append(merged)

    if not enriched:
        return _volume_ratio_from_tushare_only(pool_size, weight=weight)

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
        reason_builder=lambda row, rank: f"量比：{float(row.get('volume_ratio') or 0):.2f}，排名第 {rank}",
    ), snapshot.total


def _load_volume_ratio_map() -> dict[str, float]:
    try:
        basic_rows, _ = fetch_daily_basic()
    except Exception:
        return {}
    return {
        str(row.get("vt_symbol") or ""): float(row.get("volume_ratio") or 0)
        for row in basic_rows
        if row.get("vt_symbol") and float(row.get("volume_ratio") or 0) > 0
    }


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
    sorted_rows = sorted(
        [row for row in basic_rows if float(row.get("volume_ratio") or 0) > 0],
        key=lambda item: float(item.get("volume_ratio") or 0),
        reverse=True,
    )[:pool_size]
    hits: list[DimensionHit] = []
    for index, row in enumerate(sorted_rows, start=1):
        vt_symbol = str(row.get("vt_symbol") or "")
        if not vt_symbol:
            continue
        ratio = float(row.get("volume_ratio") or 0)
        hits.append(
            DimensionHit(
                vt_symbol=vt_symbol,
                dimension_id="volume_ratio",
                label="量比",
                weight=weight,
                score=rank_score(index, len(sorted_rows)),
                reason=f"量比：{ratio:.2f}（Tushare），排名第 {index}",
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
