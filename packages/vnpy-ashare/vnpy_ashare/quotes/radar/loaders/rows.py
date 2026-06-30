"""RadarRow 构建与指标格式化。"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from vnpy_ashare.domain.core.numbers import float_or_none
from vnpy_ashare.domain.market.quote_row import QuoteRowLike
from vnpy_ashare.domain.screener.result_row import ScreenerResultRow, screening_row_to_dict
from vnpy_ashare.domain.symbols.stock import StockItem, parse_stock_symbol
from vnpy_ashare.quotes.format import format_amount, format_pct, format_volume
from vnpy_ashare.quotes.market.moneyflow_kind import classify_moneyflow_row, flow_kind_label
from vnpy_ashare.quotes.radar.radar_models import RadarRow, merge_row_quotes
from vnpy_ashare.quotes.radar.radar_pool import name_map_for_symbols
from vnpy_ashare.quotes.radar.radar_relative_strength import build_relative_strength_subline


def radar_source_payload(row: QuoteRowLike | ScreenerResultRow) -> dict[str, Any]:
    """选股结果行 / 行情行 → plain dict（供 merge_row_quotes / RadarRow 构建）。"""
    return screening_row_to_dict(row)


def discovery_pool_size(top_n: int) -> int:
    """发现卡多取候选，硬过滤 ST 后仍能凑满 top_n。"""
    return min(max(top_n * 5, top_n + 12), 50)


def screener_metric(row: dict[str, Any]) -> tuple[str, str, str, str]:
    if "composite_score" in row:
        score = float_or_none(row.get("composite_score"))
        turnover = float_or_none(row.get("turnover_rate"))
        return (
            "综合分",
            f"{score:.1f}" if score is not None else "—",
            "换手",
            f"{turnover:.2f}%" if turnover is not None else "—",
        )
    turnover = float_or_none(row.get("turnover_rate"))
    if turnover is not None:
        return "换手", f"{turnover:.2f}%", "", ""
    amount = float(row.get("amount") or 0)
    if amount > 0:
        return "成交额", format_amount(amount), "", ""
    volume = float(row.get("volume") or 0)
    if volume > 0:
        return "成交量", format_volume(volume), "", ""
    return "", "", "", ""


def liquidity_metric(row: dict[str, Any]) -> tuple[str, str, str, str]:
    merged = merge_row_quotes(row)
    volume = float(merged.get("volume") or 0)
    amount = float(merged.get("amount") or 0)
    volume_ratio = float(merged.get("volume_ratio") or 0)
    change = float_or_none(merged.get("change_pct"))
    turnover = float_or_none(merged.get("turnover_rate"))
    if volume > 0:
        return "成交量", format_volume(volume), "涨幅", format_pct(change)
    if amount > 0:
        return "成交额", format_amount(amount), "涨幅", format_pct(change)
    if volume_ratio > 0:
        return "量比", f"{volume_ratio:.2f}", "涨幅", format_pct(change)
    return "涨幅", format_pct(change), "换手", f"{turnover:.2f}%" if turnover is not None else "—"


def moneyflow_metric(row: dict[str, Any], _hit=None) -> tuple[str, str, str, str]:
    merged = merge_row_quotes(row)
    kind = classify_moneyflow_row(merged)
    kind_label = flow_kind_label(kind)
    net_mf = float_or_none(merged.get("net_mf_amount"))
    change = float_or_none(merged.get("change_pct"))

    if kind == "proxy":
        amount = float(merged.get("amount") or 0)
        if amount > 0:
            return "成交额", format_amount(amount), kind_label, format_pct(change)
        turnover = float_or_none(merged.get("turnover_rate"))
        return "涨幅", format_pct(change), kind_label, f"{turnover:.2f}%" if turnover is not None else "—"

    if net_mf is not None and net_mf != 0:
        return "主力净流入", f"{net_mf:,.0f} 万", kind_label, format_pct(change)
    amount = float(merged.get("amount") or 0)
    if amount > 0:
        return "成交额", format_amount(amount), kind_label, format_pct(change)
    turnover = float_or_none(merged.get("turnover_rate"))
    return "涨幅", format_pct(change), kind_label, f"{turnover:.2f}%" if turnover is not None else "—"


def looks_like_vt_symbol(text: str) -> bool:
    if "." not in text:
        return False
    _code, suffix = text.rsplit(".", 1)
    return suffix.upper() in {"SSE", "SZSE", "BSE", "SH", "SZ", "BJ"}


def resolve_row_display_name(
    vt_symbol: str,
    row: dict[str, Any],
    merged: dict[str, Any],
    *,
    item: StockItem | None,
    name_map: dict[str, str],
) -> str:
    for candidate in (
        str(merged.get("name") or "").strip(),
        str(row.get("name") or "").strip(),
        str(name_map.get(vt_symbol) or "").strip(),
        (item.name if item else "").strip(),
    ):
        if candidate and candidate != vt_symbol and not looks_like_vt_symbol(candidate):
            return candidate
    if item is not None:
        return item.symbol
    return vt_symbol.split(".")[0]


def row_from_dict(row: QuoteRowLike | ScreenerResultRow, *, name_map: dict[str, str] | None = None) -> RadarRow | None:
    payload = radar_source_payload(row)
    vt_symbol = str(payload.get("vt_symbol") or "").strip()
    if not vt_symbol:
        return None
    item = parse_stock_symbol(vt_symbol)
    merged = merge_row_quotes(payload)
    lookup = name_map or {}
    name = resolve_row_display_name(vt_symbol, payload, merged, item=item, name_map=lookup)
    symbol = str(payload.get("symbol") or (item.symbol if item else vt_symbol.split(".")[0]))
    price = float_or_none(merged.get("last_price") or merged.get("close"))
    change_pct = float_or_none(merged.get("change_pct") or payload.get("change_pct") or payload.get("pct_chg"))
    metric_label, metric_value, sub_label, sub_value = screener_metric(merged)
    rs_sub = relative_strength_subline(merged)
    if rs_sub is not None:
        sub_label, sub_value = rs_sub
    return RadarRow(
        vt_symbol=vt_symbol,
        name=name,
        symbol=symbol,
        price=price,
        change_pct=change_pct,
        metric_label=metric_label,
        metric_value=metric_value,
        sub_label=sub_label,
        sub_value=sub_value,
    )


def relative_strength_subline(row: dict[str, Any]) -> tuple[str, str] | None:
    return build_relative_strength_subline(row)


def rows_from_screener(rows: Sequence[ScreenerResultRow], *, top_n: int) -> tuple[RadarRow, ...]:
    batch = rows[:top_n]
    vt_symbols = [str(radar_source_payload(row).get("vt_symbol") or "").strip() for row in batch]
    batch_name_map = name_map_for_symbols([vt for vt in vt_symbols if vt])
    result: list[RadarRow] = []
    for row in batch:
        parsed = row_from_dict(row, name_map=batch_name_map)
        if parsed is not None:
            result.append(parsed)
    return tuple(result)
