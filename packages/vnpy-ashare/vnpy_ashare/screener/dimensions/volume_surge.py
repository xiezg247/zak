"""放量维度：相对成交量（量比 / 成交额）排行。"""

from __future__ import annotations

from typing import Any

from vnpy_ashare.screener.data.data_source import load_screening_quote_snapshot
from vnpy_ashare.screener.data.quotes_loader import MarketQuotesLoadError
from vnpy_ashare.screener.data.screening_context import get_volume_ratio_map
from vnpy_ashare.screener.dimensions.base import DimensionHit, quote_hits
from vnpy_ashare.screener.hard_filters import apply_screening_filters
from vnpy_ashare.screener.preset.rules import _quote_row


def run_volume_surge(pool_size: int, *, weight: float) -> tuple[list[DimensionHit], int]:
    try:
        snapshot = load_screening_quote_snapshot()
    except MarketQuotesLoadError:
        return [], 0

    ratio_map = get_volume_ratio_map()
    enriched: list[dict[str, Any]] = []
    for row in snapshot.rows:
        vt_symbol = str(row.get("vt_symbol") or "")
        if not vt_symbol:
            continue
        merged = dict(row)
        ratio = float(ratio_map.get(vt_symbol) or merged.get("volume_ratio") or 0)
        if ratio > 0:
            merged["volume_ratio"] = ratio
            merged["relative_volume"] = ratio
        else:
            volume = float(merged.get("volume") or 0)
            amount = float(merged.get("amount") or 0)
            if volume > 0:
                merged["relative_volume"] = volume
            elif amount > 0:
                merged["relative_volume"] = amount
            else:
                continue
        enriched.append(merged)

    if not enriched:
        return [], snapshot.total

    filtered = apply_screening_filters(enriched)
    filtered.sort(key=lambda item: float(item.get("relative_volume") or 0), reverse=True)
    rows: list[dict[str, Any]] = []
    for item in filtered[:pool_size]:
        base = _quote_row(item)
        base["volume_ratio"] = float(item.get("volume_ratio") or 0)
        base["relative_volume"] = float(item.get("relative_volume") or 0)
        rows.append(base)

    return quote_hits(
        rows,
        dimension_id="volume_surge",
        label="放量",
        weight=weight,
        metric_key="relative_volume",
        reason_builder=_volume_surge_reason,
    ), snapshot.total


def _volume_surge_reason(row: dict[str, Any], rank: int) -> str:
    ratio = float(row.get("volume_ratio") or 0)
    relative = float(row.get("relative_volume") or 0)
    if ratio > 0:
        return f"放量：量比 {ratio:.2f}，相对量 {relative:.2f}，排名第 {rank}"
    volume = float(row.get("volume") or 0)
    if volume > 0:
        return f"放量：成交量 {volume:,.0f}，排名第 {rank}"
    amount = float(row.get("amount") or 0)
    return f"放量：成交额 {amount:,.0f}，排名第 {rank}"
