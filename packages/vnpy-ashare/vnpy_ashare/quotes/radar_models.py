"""雷达页共享数据模型与行情合并工具。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from vnpy_ashare.ai.context.store import get_market_quotes_cache


@dataclass(frozen=True)
class RadarRow:
    vt_symbol: str
    name: str
    symbol: str
    price: float | None
    change_pct: float | None
    metric_label: str
    metric_value: str
    sub_label: str
    sub_value: str


@dataclass(frozen=True)
class RadarCardData:
    card_id: str
    title: str
    subtitle: str
    rows: tuple[RadarRow, ...]
    empty_message: str
    updated_at: str
    run_id: str = ""
    detail_page_key: str = ""
    total_count: int = 0
    ai_hint: str = ""


def quote_map() -> dict[str, dict[str, Any]]:
    cached = get_market_quotes_cache()
    if not cached:
        return {}
    return {str(row.get("vt_symbol") or ""): row for row in cached if row.get("vt_symbol")}


def float_or_none(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None


def format_pct(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:+.2f}%"


def merge_row_quotes(row: dict[str, Any]) -> dict[str, Any]:
    """合并行情缓存，补全 volume / amount / 现价等字段。"""
    vt_symbol = str(row.get("vt_symbol") or "").strip()
    merged = dict(row)
    quote = quote_map().get(vt_symbol, {})
    for key in (
        "volume",
        "amount",
        "change_pct",
        "last_price",
        "close",
        "turnover_rate",
        "volume_ratio",
        "net_mf_amount",
        "name",
    ):
        cached = quote.get(key)
        if cached in (None, "", 0, 0.0):
            continue
        if not merged.get(key):
            merged[key] = cached
    return merged
