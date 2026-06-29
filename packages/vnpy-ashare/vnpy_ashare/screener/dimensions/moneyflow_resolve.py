"""资金流命中统一解析（盘中 MCP 优先 / 盘后 Tushare 优先）。"""

from __future__ import annotations

from typing import Any

from vnpy_ashare.domain.market.quote_row import QuoteRow, QuoteRowLike, QuoteRowsLike, quote_row_copy
from vnpy_ashare.domain.time.market_hours import is_ashare_trading_session
from vnpy_ashare.integrations.mcp.intraday_flow import fetch_intraday_moneyflow_map
from vnpy_ashare.quotes.core.quote_rows import quote_rows_by_vt_symbol
from vnpy_ashare.quotes.market.moneyflow_kind import enrich_moneyflow_row_with_kind
from vnpy_ashare.screener.data.data_source import fetch_moneyflow_with_fallback, load_screening_quote_snapshot
from vnpy_ashare.screener.data.quotes_loader import MarketQuotesLoadError, MarketQuotesSnapshot
from vnpy_ashare.screener.dimensions.base import DimensionHit, dimension_hit_row, rank_score

_INTRADAY_DIMENSION_ID = "moneyflow_intraday"
_INTRADAY_LABEL = "盘中资金"
_POST_LABEL = "资金"
_DIVERGENCE_SCORE_FACTOR = 0.65
_STREAK_BONUS_PER_DAY = 0.05
_MAX_STREAK_BONUS = 0.2
_STREAK_TIER_3_BONUS = 0.08
_STREAK_TIER_5_BONUS = 0.15


def _moneyflow_score_adjustment(row: dict[str, Any], base_score: float) -> float:
    change = float(row.get("change_pct") or row.get("pct_chg") or 0)
    net = float(row.get("net_mf_amount") or 0)
    score = base_score
    if net > 0 and change < -0.5:
        score *= _DIVERGENCE_SCORE_FACTOR
    streak = int(row.get("moneyflow_streak_days") or 0)
    if streak >= 5:
        score *= 1.0 + _STREAK_TIER_5_BONUS
    elif streak >= 3:
        score *= 1.0 + _STREAK_TIER_3_BONUS
    elif streak >= 2:
        score *= 1.0 + min(_MAX_STREAK_BONUS, (streak - 1) * _STREAK_BONUS_PER_DAY)
    return score


def count_positive_moneyflow_streak(vt_symbol: str, *, max_days: int = 5) -> int:
    """连续净流入天数（仅读本地 Tushare 缓存，无缓存则跳过）。"""
    from vnpy_ashare.screener.engine.dimensions.moneyflow_streak import build_positive_moneyflow_streak_map

    vt = str(vt_symbol or "").strip()
    if not vt:
        return 0
    return build_positive_moneyflow_streak_map({vt}, max_days=max_days).get(vt, 0)


def resolve_moneyflow_hits(
    pool_size: int,
    *,
    weight: float = 1.0,
    enrich_kind: bool = False,
) -> tuple[list[DimensionHit], int, str]:
    """
    统一降级链：
    - 盘中：MCP 主力净流入 → 成交额+涨幅代理
    - 盘后：Tushare moneyflow → 成交额+涨幅代理

    返回 (hits, total_scanned, trade_date)；trade_date 仅盘后 Tushare 命中时有值。
    """
    snapshot = _try_quote_snapshot()
    quote_map = _quote_map_from_snapshot(snapshot)
    total = snapshot.total if snapshot is not None else 0

    if is_ashare_trading_session():
        hits, total = _intraday_hits(pool_size, snapshot, weight=weight, total=total)
        if enrich_kind and hits:
            hits = _enrich_hits_with_kind(hits, quote_map)
        return hits, total, ""

    hits, total, trade_date = _post_close_tushare_hits(pool_size, quote_map, weight=weight, total=total)
    if hits:
        if enrich_kind:
            hits = _enrich_hits_with_kind(hits, quote_map)
        return hits, total, trade_date

    hits, total = _turnover_proxy_hits(pool_size, snapshot, weight=weight, total=total)
    if enrich_kind and hits:
        hits = _enrich_hits_with_kind(hits, quote_map)
    return hits, total, ""


def _try_quote_snapshot() -> MarketQuotesSnapshot | None:
    try:
        return load_screening_quote_snapshot()
    except MarketQuotesLoadError:
        return None


def _quote_map_from_snapshot(snapshot: MarketQuotesSnapshot | None) -> dict[str, QuoteRow]:
    if snapshot is None:
        return {}
    return quote_rows_by_vt_symbol(snapshot.rows)


def _intraday_hits(
    pool_size: int,
    snapshot: MarketQuotesSnapshot | None,
    *,
    weight: float,
    total: int,
) -> tuple[list[DimensionHit], int]:
    if snapshot is None:
        return [], total

    mcp_map = fetch_intraday_moneyflow_map(snapshot.rows, top_n=pool_size * 2)
    if mcp_map:
        return _hits_from_mcp_map(mcp_map, snapshot.rows, pool_size, weight=weight), snapshot.total
    return _hits_from_proxy(snapshot.rows, pool_size, weight=weight), snapshot.total


def _post_close_tushare_hits(
    pool_size: int,
    quote_map: dict[str, QuoteRow],
    *,
    weight: float,
    total: int,
) -> tuple[list[DimensionHit], int, str]:
    raw_rows, trade_date = fetch_moneyflow_with_fallback()
    if not raw_rows:
        return [], total, ""

    from vnpy_ashare.screener.engine.dimensions.moneyflow_post import (
        post_close_streak_map_for_rows,
        rank_post_close_moneyflow_rows_polars,
    )

    ranked = rank_post_close_moneyflow_rows_polars(raw_rows, pool_size=pool_size)
    streak_map = post_close_streak_map_for_rows(ranked)

    hits: list[DimensionHit] = []
    for index, row in enumerate(ranked, start=1):
        vt_symbol = str(row.get("vt_symbol") or "")
        if not vt_symbol:
            continue
        amount = float(row.get("net_mf_amount") or 0)
        merged = _merge_quote_fields(row, quote_map.get(vt_symbol))
        merged["moneyflow_source"] = row.get("moneyflow_source", "tushare")
        streak = streak_map.get(vt_symbol, 0)
        if streak:
            merged["moneyflow_streak_days"] = streak
        base_score = rank_score(index, len(ranked))
        adjusted = _moneyflow_score_adjustment(merged, base_score)
        divergence_note = ""
        change = float(merged.get("change_pct") or merged.get("pct_chg") or 0)
        if amount > 0 and change < -0.5:
            divergence_note = "（价量背离降权）"
        streak_note = ""
        if streak >= 5:
            streak_note = f"，连涨 {streak} 日"
        elif streak >= 3:
            streak_note = f"，连涨 {streak} 日"
        elif streak >= 2:
            streak_note = f"，连涨 {streak} 日"
        hits.append(
            DimensionHit(
                vt_symbol=vt_symbol,
                dimension_id="moneyflow",
                label=_POST_LABEL,
                weight=weight,
                score=round(adjusted, 1),
                reason=f"资金：主力净流入 {amount:,.0f} 万{streak_note}{divergence_note}，排名第 {index}",
                row=dimension_hit_row(merged),
            )
        )
    return hits, len(raw_rows), trade_date


def _turnover_proxy_hits(
    pool_size: int,
    snapshot: MarketQuotesSnapshot | None,
    *,
    weight: float,
    total: int,
) -> tuple[list[DimensionHit], int]:
    if snapshot is None:
        try:
            snapshot = load_screening_quote_snapshot()
        except MarketQuotesLoadError:
            return [], total

    return _hits_from_proxy(snapshot.rows, pool_size, weight=weight), snapshot.total


def _hits_from_mcp_map(
    flow_map: dict[str, float],
    rows: QuoteRowsLike,
    pool_size: int,
    *,
    weight: float,
) -> list[DimensionHit]:
    row_by_vt = quote_rows_by_vt_symbol(rows)
    ranked = sorted(flow_map.items(), key=lambda item: item[1], reverse=True)[:pool_size]
    hits: list[DimensionHit] = []
    for index, (vt_symbol, amount) in enumerate(ranked, start=1):
        base = row_by_vt.get(vt_symbol)
        if base is None:
            continue
        merged = quote_row_copy(base, net_mf_amount=amount)
        hits.append(
            DimensionHit(
                vt_symbol=vt_symbol,
                dimension_id=_INTRADAY_DIMENSION_ID,
                label=_INTRADAY_LABEL,
                weight=weight,
                score=round(_moneyflow_score_adjustment(merged.to_dict(), rank_score(index, len(ranked))), 1),
                reason=f"盘中资金：主力净流入 {amount:,.0f} 万，排名第 {index}",
                row=dimension_hit_row(merged),
            )
        )
    return hits


def _hits_from_proxy(
    rows: QuoteRowsLike,
    pool_size: int,
    *,
    weight: float,
) -> list[DimensionHit]:
    from vnpy_ashare.screener.engine.dimensions.moneyflow_proxy import hits_from_moneyflow_proxy_polars

    return hits_from_moneyflow_proxy_polars(list(rows), pool_size, weight=weight)


def _merge_quote_fields(row: QuoteRowLike, quote_row: QuoteRowLike | None) -> dict[str, Any]:
    item = dict(row)
    if quote_row is not None:
        for key in (
            "change_pct",
            "pct_chg",
            "turnover_rate",
            "last_price",
            "close",
            "amount",
            "volume",
            "name",
        ):
            value = quote_row.get(key)
            if value not in (None, ""):
                item[key] = value
    return item


def _enrich_hits_with_kind(
    hits: list[DimensionHit],
    quote_map: dict[str, QuoteRow],
) -> list[DimensionHit]:
    enriched: list[DimensionHit] = []
    for hit in hits:
        merged = _merge_quote_fields(hit.row.to_dict(), quote_map.get(hit.vt_symbol))
        if hit.dimension_id == _INTRADAY_DIMENSION_ID and "代理" in hit.reason:
            merged["moneyflow_proxy"] = True
        row = enrich_moneyflow_row_with_kind(merged)
        enriched.append(
            DimensionHit(
                vt_symbol=hit.vt_symbol,
                dimension_id=hit.dimension_id,
                label=hit.label,
                weight=hit.weight,
                score=hit.score,
                reason=hit.reason,
                row=dimension_hit_row(row),
            )
        )
    return enriched


def build_moneyflow_source_subtitle(
    hits: list[DimensionHit],
    trade_date: str,
) -> str:
    """雷达副标题：标注 Tushare 交易日 / MCP 盘中 / 成交额代理。"""
    if trade_date:
        return f" · Tushare {trade_date}"
    if not hits:
        return ""

    has_proxy = any(hit.row.get("moneyflow_proxy") or "代理" in hit.reason for hit in hits)
    if has_proxy:
        return " · 成交额代理"

    first = hits[0]
    if first.dimension_id == _INTRADAY_DIMENSION_ID:
        return " · MCP 盘中"
    if first.dimension_id == "moneyflow":
        return " · Tushare 盘后"
    return ""
