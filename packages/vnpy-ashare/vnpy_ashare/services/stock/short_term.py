"""个股短线（打板 / 龙头）画像。"""

from __future__ import annotations

from typing import Any

from vnpy_ashare.ai.context.symbol import parse_stock_symbol
from vnpy_ashare.domain.stock.short_term import (
    LimitHistoryRow,
    LimitStats,
    ShortTermPeer,
    ShortTermProfile,
    TopInstRow,
    TopListRow,
)
from vnpy_ashare.integrations.tushare.limit_list_fallback import (
    fetch_limit_list_with_fallback,
    fetch_symbol_limit_history,
)
from vnpy_ashare.integrations.tushare.top_list import (
    fetch_top_inst_for_date,
    fetch_top_list_history,
)
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
from vnpy_ashare.trading.signals.intraday_seal_time import attach_first_time_fields
from vnpy_ashare.trading.signals.seal_reopen import attach_seal_reopen_fields, seal_reopen_from_row
from vnpy_ashare.trading.signals.seal_strength import seal_strength_from_row

_LIMIT_HISTORY_DAYS = 20
_TOP_LIST_LOOKBACK_DAYS = 30


def _seal_strength_label(score: float | None) -> str:
    if score is None or score <= 0:
        return "—"
    if score >= 0.8:
        return "强"
    if score >= 0.55:
        return "中"
    return "弱"


def _build_limit_history(ts_code: str, vt_symbol: str) -> tuple[list[LimitHistoryRow], LimitStats]:
    raw_rows = fetch_symbol_limit_history(
        ts_code=ts_code,
        vt_symbol=vt_symbol,
        limit_type="U",
        max_days=_LIMIT_HISTORY_DAYS,
    )
    history: list[LimitHistoryRow] = []
    open_board_days = 0
    solid_seal_days = 0
    for row in raw_rows:
        open_raw = row.get("open_times")
        open_times: int | None = None
        if open_raw not in (None, "") and isinstance(open_raw, (int, float, str)):
            try:
                open_times = int(float(open_raw))
            except (TypeError, ValueError):
                open_times = None
        if open_times is not None and open_times > 0:
            open_board_days += 1
        elif open_times == 0:
            solid_seal_days += 1

        limit_times_raw = row.get("limit_times")
        limit_times = float(limit_times_raw) if isinstance(limit_times_raw, (int, float)) else None
        fd_raw = row.get("fd_amount")
        fd_amount = float(fd_raw) if isinstance(fd_raw, (int, float)) else None
        strth_raw = row.get("strth")
        strth = float(strth_raw) if isinstance(strth_raw, (int, float)) else None
        history.append(
            LimitHistoryRow(
                trade_date=str(row.get("trade_date") or ""),
                limit_times=limit_times,
                first_time=str(row.get("first_time") or ""),
                last_time=str(row.get("last_time") or ""),
                fd_amount=fd_amount,
                open_times=open_times,
                strth=strth,
            )
        )

    stats = LimitStats(
        lookback_days=_LIMIT_HISTORY_DAYS,
        limit_up_days=len(history),
        open_board_days=open_board_days,
        solid_seal_days=solid_seal_days,
    )
    return history, stats


def _build_top_list(ts_code: str) -> tuple[list[TopListRow], list[TopInstRow], list[TopInstRow], str]:
    raw_rows = fetch_top_list_history(ts_code, max_days=_TOP_LIST_LOOKBACK_DAYS, limit=8)
    top_rows: list[TopListRow] = []
    for row in raw_rows:
        top_rows.append(
            TopListRow(
                trade_date=str(row.get("trade_date") or ""),
                close=row.get("close"),
                pct_change=row.get("pct_change"),
                turnover_rate=row.get("turnover_rate"),
                net_amount=row.get("net_amount"),
                net_rate=row.get("net_rate"),
                reason=str(row.get("reason") or ""),
            )
        )

    inst_date = top_rows[0].trade_date if top_rows else ""
    buys: list[TopInstRow] = []
    sells: list[TopInstRow] = []
    if inst_date:
        raw_buys, raw_sells = fetch_top_inst_for_date(trade_date=inst_date, ts_code=ts_code)
        buys = [
            TopInstRow(
                exalter=str(item.get("exalter") or ""),
                buy=item.get("buy"),
                sell=item.get("sell"),
                net_buy=item.get("net_buy"),
            )
            for item in raw_buys
        ]
        sells = [
            TopInstRow(
                exalter=str(item.get("exalter") or ""),
                buy=item.get("buy"),
                sell=item.get("sell"),
                net_buy=item.get("net_buy"),
            )
            for item in raw_sells
        ]
    return top_rows, buys, sells, inst_date


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
    """今日涨停详情（单项）；先查缓存，未涨停直接跳过避免全市场查询。"""
    # 若本地连板缓存显示未涨停，直接跳过
    limit_map = get_cached_limit_times_map()
    item = parse_stock_symbol(vt_symbol)
    if item is not None:
        boards = limit_map.get(item.tickflow_symbol, 0)
        if boards < 1:
            return None, ""
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
                change_pct=float(row.get("change_pct")) if isinstance(row.get("change_pct"), (int, float)) else None,
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
    seal_score = seal_strength_from_row(row)
    _reopen_kind, reopen_label, _reopen_score, _open_times = seal_reopen_from_row(row)
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

    limit_history, limit_stats = _build_limit_history(item.ts_code, item.vt_symbol)
    top_list, top_inst_buy, top_inst_sell, top_inst_date = _build_top_list(item.ts_code)

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
        seal_strength=seal_score if seal_score > 0 else None,
        seal_strength_label=_seal_strength_label(seal_score if seal_score > 0 else None),
        seal_reopen_label=str(reopen_label or row.get("seal_reopen_label") or ""),
        limit_history=limit_history,
        limit_stats=limit_stats,
        leader_tier=leader_tier,
        leader_tier_label=leader_tier_label(leader_tier),
        sector_name=sector_name,
        sector_rank=sector_rank,
        sector_peers=sector_peers,
        entry_mode=entry_dict,
        top_list=top_list,
        top_inst_buy=top_inst_buy,
        top_inst_sell=top_inst_sell,
        top_inst_date=top_inst_date,
        regulatory_summary=regulatory_summary,
        regulatory_risk_level=regulatory_risk,
        message=message,
    )
