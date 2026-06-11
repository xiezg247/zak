"""盘中资金维度：优先 TDX MCP 主力净流入，不可用时成交额+涨幅代理。"""

from __future__ import annotations

from typing import Any

from vnpy_ashare.integrations.mcp.intraday_flow import fetch_intraday_moneyflow_map
from vnpy_ashare.screener.data.data_source import load_screening_quote_snapshot
from vnpy_ashare.screener.data.quotes_loader import MarketQuotesLoadError
from vnpy_ashare.screener.dimensions.base import DimensionHit, rank_score

_META_DIMENSION_ID = "moneyflow_intraday"


def run_moneyflow_intraday(pool_size: int, *, weight: float) -> tuple[list[DimensionHit], int]:
    try:
        snapshot = load_screening_quote_snapshot()
    except MarketQuotesLoadError:
        return [], 0

    mcp_map = fetch_intraday_moneyflow_map(snapshot.rows, top_n=pool_size * 2)
    if mcp_map:
        return _hits_from_mcp_map(mcp_map, snapshot.rows, pool_size, weight=weight), snapshot.total
    return _hits_from_proxy(snapshot.rows, pool_size, weight=weight), snapshot.total


def _hits_from_mcp_map(
    flow_map: dict[str, float],
    rows: list[dict[str, Any]],
    pool_size: int,
    *,
    weight: float,
) -> list[DimensionHit]:
    row_by_vt = {str(row.get("vt_symbol") or ""): row for row in rows}
    ranked = sorted(flow_map.items(), key=lambda item: item[1], reverse=True)[:pool_size]
    hits: list[DimensionHit] = []
    for index, (vt_symbol, amount) in enumerate(ranked, start=1):
        base = row_by_vt.get(vt_symbol)
        if base is None:
            continue
        merged = dict(base)
        merged["net_mf_amount"] = amount
        hits.append(
            DimensionHit(
                vt_symbol=vt_symbol,
                dimension_id=_META_DIMENSION_ID,
                label="盘中资金",
                weight=weight,
                score=rank_score(index, len(ranked)),
                reason=f"盘中资金：主力净流入 {amount:,.0f} 万，排名第 {index}",
                row=merged,
            )
        )
    return hits


def _hits_from_proxy(
    rows: list[dict[str, Any]],
    pool_size: int,
    *,
    weight: float,
) -> list[DimensionHit]:
    scored: list[tuple[dict[str, Any], float]] = []
    for row in rows:
        change = max(float(row.get("change_pct") or 0), 0.0)
        amount = float(row.get("amount") or 0)
        if amount <= 0 or change <= 0:
            continue
        scored.append((row, change * amount))
    scored.sort(key=lambda item: item[1], reverse=True)
    hits: list[DimensionHit] = []
    for index, (row, _proxy) in enumerate(scored[:pool_size], start=1):
        vt_symbol = str(row.get("vt_symbol") or "")
        if not vt_symbol:
            continue
        amount = float(row.get("amount") or 0) / 1e4
        hits.append(
            DimensionHit(
                vt_symbol=vt_symbol,
                dimension_id=_META_DIMENSION_ID,
                label="盘中资金",
                weight=weight,
                score=rank_score(index, min(len(scored), pool_size)),
                reason=(f"盘中资金：涨幅 {float(row.get('change_pct') or 0):+.2f}% + 成交额 {amount:,.0f} 万（代理），排名第 {index}"),
                row=dict(row),
            )
        )
    return hits
