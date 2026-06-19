"""个股短线（打板 / 龙头）画像。"""

from __future__ import annotations

from typing import Any

from vnpy_ashare.ai.context.symbol import parse_stock_symbol
from vnpy_ashare.domain.stock.short_term import ShortTermPeer, ShortTermProfile
from vnpy_ashare.integrations.tushare.limit_list_fallback import fetch_limit_list_with_fallback
from vnpy_ashare.quotes.analysis.entry_mode import evaluate_entry_mode
from vnpy_ashare.quotes.core.limit_times_cache import get_cached_limit_times_map
from vnpy_ashare.quotes.market.emotion_cycle import load_emotion_cycle_snapshot
from vnpy_ashare.quotes.radar.radar_leader import leader_tier_label, rank_sector_leaders
from vnpy_ashare.quotes.radar.radar_limit_ladder import resolve_limit_times
from vnpy_ashare.quotes.radar.radar_models import merge_row_quotes, quotes_for_vt_symbols
from vnpy_ashare.screener.data.data_source import load_screening_quote_snapshot
from vnpy_ashare.screener.data.quotes_loader import MarketQuotesLoadError
from vnpy_ashare.screener.sector.sector_summary import attach_sector_fields
from vnpy_ashare.services.stock.regulatory_deviation import assess_regulatory_deviation_for_vt_symbol
from vnpy_ashare.trading.signals.seal_reopen import attach_seal_reopen_fields
from vnpy_ashare.trading.signals.intraday_seal_time import attach_first_time_fields


def _merge_quote_row(vt_symbol: str, *, quote_summary: dict[str, Any] | None = None) -> dict[str, Any]:
    item = parse_stock_symbol(vt_symbol)
    symbol = item.symbol if item is not None else vt_symbol.split(".")[0]
    quotes = quotes_for_vt_symbols([vt_symbol])
    row = merge_row_quotes(
        quotes.get(
            vt_symbol,
            {
                "vt_symbol": vt_symbol,
                "symbol": symbol,
                "name": item.name if item is not None else symbol,
            },
        )
    )
    if quote_summary:
        for key, value in quote_summary.items():
            if value is not None and value != "":
                row[key] = value
    return row


def _find_limit_today(vt_symbol: str) -> tuple[dict[str, Any] | None, str]:
    rows, trade_date = fetch_limit_list_with_fallback(limit_type="U")
    for row in rows:
        if str(row.get("vt_symbol") or "").strip() == vt_symbol:
            return row, trade_date
    return None, trade_date


def _resolve_sector_leaders(
    vt_symbol: str,
    *,
    target_industry: str = "",
) -> tuple[str, str, int, list[ShortTermPeer]]:
    try:
        snapshot = load_screening_quote_snapshot()
    except MarketQuotesLoadError:
        return target_industry, "", 0, []

    enriched, _hot = attach_sector_fields(snapshot.rows)
    if not enriched:
        return target_industry, "", 0, []

    industry = target_industry.strip()
    if not industry:
        for row in enriched:
            if str(row.get("vt_symbol") or "").strip() == vt_symbol:
                industry = str(row.get("industry") or "").strip()
                break
    if not industry:
        return "", "", 0, []

    peers = [dict(row) for row in enriched if str(row.get("industry") or "").strip() == industry]
    if not peers:
        return industry, "", 0, []

    attach_first_time_fields(peers)
    scored_list = rank_sector_leaders(peers, sector_key="industry", max_per_sector=8)

    leader_tier = ""
    sector_rank = 0
    for index, scored in enumerate(scored_list, start=1):
        if str(scored.row.get("vt_symbol") or "").strip() == vt_symbol:
            leader_tier = scored.leader_tier
            sector_rank = index
            break

    peer_models: list[ShortTermPeer] = []
    for scored in scored_list[:5]:
        row = scored.row
        peer_models.append(
            ShortTermPeer(
                vt_symbol=str(row.get("vt_symbol") or ""),
                name=str(row.get("name") or row.get("symbol") or ""),
                leader_tier=scored.leader_tier,
                leader_tier_label=leader_tier_label(scored.leader_tier),
                limit_times=scored.limit_times,
                change_pct=float(row.get("change_pct"))
                if isinstance(row.get("change_pct"), (int, float))
                else None,
            )
        )
    return industry, leader_tier, sector_rank, peer_models


def build_short_term_profile(
    vt_symbol: str,
    *,
    quote_summary: dict[str, Any] | None = None,
) -> ShortTermProfile:
    """聚合涨停档案、龙头地位、买点模式与监管异动。"""
    item = parse_stock_symbol(vt_symbol)
    if item is None:
        return ShortTermProfile(
            ts_code="",
            vt_symbol=vt_symbol,
            message=f"无法解析代码: {vt_symbol}",
        )

    row = _merge_quote_row(vt_symbol, quote_summary=quote_summary)
    limit_today, trade_date = _find_limit_today(vt_symbol)
    if limit_today:
        for key in ("limit_times", "first_time", "last_time", "fd_amount", "open_times", "strth", "limit"):
            value = limit_today.get(key)
            if value is not None and value != "":
                row[key] = value

    limit_map = get_cached_limit_times_map()
    boards = resolve_limit_times(row, limit_times_map=limit_map)
    if boards >= 1:
        row["limit_times"] = boards

    attach_seal_reopen_fields(row)
    industry = str(row.get("industry") or "").strip()
    sector_name, leader_tier, sector_rank, sector_peers = _resolve_sector_leaders(
        vt_symbol,
        target_industry=industry,
    )
    if sector_name and not row.get("industry"):
        row["industry"] = sector_name

    cycle = load_emotion_cycle_snapshot(fetch_if_missing=True)
    entry = evaluate_entry_mode(
        row,
        cycle=cycle,
        leader_tier=leader_tier,
        limit_times=boards if boards >= 1 else None,
    )
    entry_dict = entry.to_dict() if entry is not None else {}

    regulatory = assess_regulatory_deviation_for_vt_symbol(vt_symbol)
    regulatory_summary = ""
    regulatory_risk = "none"
    if regulatory is not None:
        regulatory_summary = regulatory.summary
        regulatory_risk = regulatory.risk_level

    name = str(row.get("name") or item.name or item.symbol)
    message = ""
    if not limit_today and boards < 1:
        message = "今日未在涨停列表；仍可参考买点模式与监管异动"

    return ShortTermProfile(
        ts_code=item.ts_code,
        vt_symbol=item.vt_symbol,
        name=name,
        trade_date=trade_date,
        limit_today=limit_today,
        limit_times=boards if boards >= 1 else None,
        leader_tier=leader_tier,
        leader_tier_label=leader_tier_label(leader_tier),
        sector_name=sector_name,
        sector_rank=sector_rank,
        sector_peers=sector_peers,
        entry_mode=entry_dict,
        regulatory_summary=regulatory_summary,
        regulatory_risk_level=regulatory_risk,
        message=message,
    )
