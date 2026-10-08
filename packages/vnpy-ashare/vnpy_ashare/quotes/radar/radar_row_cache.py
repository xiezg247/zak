"""雷达行 ↔ cache schema JSON 序列化。"""

from __future__ import annotations

from typing import Any

from vnpy_ashare.domain.core.numbers import float_or_none
from vnpy_ashare.domain.radar.card import RadarRow
from vnpy_ashare.quotes.radar.radar_enrich import enrich_radar_row

__all__ = [
    "radar_row_from_cache_dict",
    "radar_row_to_cache_dict",
]


def radar_row_to_cache_dict(row: RadarRow) -> dict[str, Any]:
    """RadarRow → cache schema JSON 条目。"""
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
    if row.board_quality is not None:
        payload["board_quality"] = row.board_quality
    return payload


def radar_row_from_cache_dict(
    raw: dict[str, Any],
    *,
    quote: dict[str, Any] | None = None,
    enrich: bool = True,
) -> RadarRow:
    """cache schema JSON 条目 → RadarRow（可选合并实时行情）。"""
    vt_symbol = str(raw.get("vt_symbol") or "").strip()
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
        board_quality=float_or_none(raw.get("board_quality")),
    )
    if not enrich:
        return row
    base = quote if quote is not None else {"vt_symbol": vt_symbol}
    return enrich_radar_row(row, base)
