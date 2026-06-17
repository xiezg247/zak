"""雷达页主力资金 enrichment（Tushare + 可选 MCP）。"""

from __future__ import annotations

from typing import Any

from vnpy_ashare.domain.format import float_or_none
from vnpy_ashare.quotes.format import format_pct
from vnpy_ashare.domain.symbols import parse_stock_symbol
from vnpy_ashare.integrations.mcp.intraday_flow import fetch_intraday_moneyflow_map
from vnpy_ashare.quotes.radar.radar_models import merge_row_quotes
from vnpy_ashare.screener.data.data_source import fetch_moneyflow_with_fallback


def _moneyflow_map_from_tushare(vt_symbols: list[str]) -> dict[str, float]:
    if not vt_symbols:
        return {}
    try:

        rows, _ = fetch_moneyflow_with_fallback(max_lookback=5)
    except Exception:
        return {}

    want = set(vt_symbols)
    ts_to_vt: dict[str, str] = {}
    for vt_symbol in vt_symbols:
        item = parse_stock_symbol(vt_symbol)
        if item is not None:
            ts_to_vt[item.ts_code] = vt_symbol

    result: dict[str, float] = {}
    for row in rows:
        vt_symbol = str(row.get("vt_symbol") or "").strip()
        ts_code = str(row.get("ts_code") or "").strip()
        amount = float(row.get("net_mf_amount") or 0)
        if vt_symbol in want:
            result[vt_symbol] = amount
        elif ts_code and ts_code in ts_to_vt:
            result[ts_to_vt[ts_code]] = amount
    return result


def _moneyflow_map_from_mcp(rows: list[dict[str, Any]], *, limit: int) -> dict[str, float]:
    if not rows:
        return {}
    try:

        return fetch_intraday_moneyflow_map(rows, top_n=limit)
    except Exception:
        return {}


def enrich_quotes_with_moneyflow(
    quotes_by_vt: dict[str, dict[str, Any]],
    *,
    mcp_limit: int = 20,
) -> dict[str, dict[str, Any]]:
    """为自选行情行附加 net_mf_amount（万元）。"""
    if not quotes_by_vt:
        return quotes_by_vt

    vt_symbols = list(quotes_by_vt)
    flow_map = _moneyflow_map_from_tushare(vt_symbols)

    missing: list[dict[str, Any]] = []
    for vt_symbol, row in quotes_by_vt.items():
        if vt_symbol in flow_map:
            continue
        if float(row.get("net_mf_amount") or 0) != 0:
            continue
        missing.append(dict(row, vt_symbol=vt_symbol))

    if missing:
        flow_map.update(_moneyflow_map_from_mcp(missing, limit=mcp_limit))

    enriched: dict[str, dict[str, Any]] = {}
    for vt_symbol, row in quotes_by_vt.items():
        merged = dict(row)
        if vt_symbol in flow_map:
            merged["net_mf_amount"] = flow_map[vt_symbol]
        enriched[vt_symbol] = merged
    return enriched


def moneyflow_score_boost(row: dict[str, Any]) -> float:
    merged = merge_row_quotes(row)
    net_mf = float_or_none(merged.get("net_mf_amount"))
    if net_mf is None or net_mf <= 0:
        return 0.0
    return min(net_mf / 3000.0, 12.0)


def watchlist_moneyflow_metric(row: dict[str, Any]) -> tuple[str, str, str, str] | None:
    """有主力净流入时返回 (主指标, 主值, 副标签, 副值)。"""
    merged = merge_row_quotes(row)
    net_mf = float_or_none(merged.get("net_mf_amount"))
    if net_mf is None or net_mf == 0:
        return None
    change = float_or_none(merged.get("change_pct"))
    return "主力净流入", f"{net_mf:,.0f} 万", "涨幅", format_pct(change)
