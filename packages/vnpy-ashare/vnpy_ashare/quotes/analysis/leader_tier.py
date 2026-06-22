"""板块龙头分层解读（explain_leader_tier）。"""

from __future__ import annotations

from typing import Any

from vnpy_ashare.ai.context.symbol import parse_stock_symbol
from vnpy_ashare.quotes.core.limit_times_cache import get_cached_limit_times_map
from vnpy_ashare.quotes.radar.radar_leader import (
    FOLLOWER_MIN_SCORE,
    leader_tier_label,
    rank_sector_group_full,
    rank_sector_leaders,
)
from vnpy_ashare.quotes.radar.radar_limit_ladder import resolve_limit_times
from vnpy_ashare.screener.data.data_source import load_screening_quote_snapshot
from vnpy_ashare.screener.data.quotes_loader import MarketQuotesLoadError
from vnpy_ashare.screener.sector.sector_summary import attach_sector_fields
from vnpy_ashare.trading.signals.intraday_seal_time import attach_first_time_fields

_MAX_PER_SECTOR = 8


def _top_drivers(components: list[dict[str, Any]], *, limit: int = 3) -> list[dict[str, Any]]:
    ranked = sorted(components, key=lambda item: float(item.get("points") or 0), reverse=True)
    return ranked[:limit]


def _build_summary(
    *,
    name: str,
    sector: str,
    tier: str,
    sector_rank: int,
    leader_score: float,
    peers_ahead: list[dict[str, Any]],
    key_drivers: list[dict[str, Any]],
) -> str:
    driver_text = "、".join(f"{item.get('label')}({item.get('points')}分)" for item in key_drivers if float(item.get("points") or 0) > 0)
    if driver_text:
        driver_clause = f"主要得益于{driver_text}。"
    else:
        driver_clause = "各维度得分均偏弱。"

    if tier == "dragon_1":
        return f"{name}在「{sector}」板块内龙头分 {leader_score} 排名第 {sector_rank}，判定为龙一。{driver_clause}"
    if tier == "dragon_2":
        ahead = peers_ahead[0] if peers_ahead else None
        if ahead:
            gap = round(float(ahead.get("leader_score") or 0) - leader_score, 1)
            ahead_note = f"龙一 {ahead.get('name')} 龙头分 {ahead.get('leader_score')}，领先 {gap} 分。"
        else:
            ahead_note = ""
        return f"{name}在「{sector}」板块内龙头分 {leader_score} 排名第 {sector_rank}，判定为龙二。{ahead_note}{driver_clause}"
    if tier == "follower":
        return (
            f"{name}在「{sector}」板块内龙头分 {leader_score} 排名第 {sector_rank}，"
            f"达到跟风门槛（≥{FOLLOWER_MIN_SCORE} 且 Top{_MAX_PER_SECTOR} 内），"
            f"判定为跟风。{driver_clause}"
        )
    if sector_rank <= _MAX_PER_SECTOR and leader_score < FOLLOWER_MIN_SCORE:
        return f"{name}在「{sector}」板块内排名第 {sector_rank}，龙头分 {leader_score} 未达跟风门槛 {FOLLOWER_MIN_SCORE}，暂无龙头分层。{driver_clause}"
    return f"{name}在「{sector}」板块内排名第 {sector_rank}，龙头分 {leader_score}，未进入板块 Top{_MAX_PER_SECTOR}，暂无龙头分层。{driver_clause}"


def _build_reasons(
    *,
    tier: str,
    sector_rank: int,
    leader_score: float,
    breakdown: dict[str, Any],
    peers_ahead: list[dict[str, Any]],
) -> list[str]:
    reasons: list[str] = []
    limit_times = int(breakdown.get("limit_times") or 0)
    if limit_times >= 1:
        reasons.append(f"连板 {limit_times} 板，连板高度在龙头分中权重较高")

    for item in _top_drivers(list(breakdown.get("components") or [])):
        label = str(item.get("label") or "")
        points = float(item.get("points") or 0)
        if points >= 8:
            reasons.append(f"{label}贡献 {points} 分")

    if tier == "dragon_1":
        reasons.append("板块内龙头分排序第一 → 龙一")
    elif tier == "dragon_2":
        reasons.append("板块内龙头分排序第二 → 龙二")
        if peers_ahead:
            top = peers_ahead[0]
            reasons.append(f"龙一 {top.get('name')} 龙头分 {top.get('leader_score')}，连板 {top.get('limit_times')} 板")
    elif tier == "follower":
        reasons.append(f"Top{_MAX_PER_SECTOR} 内且龙头分 {leader_score} ≥ {FOLLOWER_MIN_SCORE} → 跟风")
    elif sector_rank <= _MAX_PER_SECTOR:
        reasons.append(f"龙头分 {leader_score} 低于跟风门槛 {FOLLOWER_MIN_SCORE}")
    else:
        reasons.append(f"板块内排名第 {sector_rank}，超出 Top{_MAX_PER_SECTOR} 分层范围")

    return reasons


def explain_leader_tier_for_symbol(symbol: str) -> dict[str, Any]:
    """解读单票在所属行业板块内的龙一/龙二/跟风判定及评分依据。"""
    item = parse_stock_symbol(symbol)
    if item is None:
        return {"error": f"无法解析代码: {symbol}"}

    vt_symbol = item.vt_symbol
    try:
        snapshot = load_screening_quote_snapshot()
    except MarketQuotesLoadError as exc:
        return {"error": f"行情快照不可用: {exc}", "vt_symbol": vt_symbol}

    enriched, _hot = attach_sector_fields(snapshot.rows)
    if not enriched:
        return {"error": "行情快照为空", "vt_symbol": vt_symbol}

    target_row: dict[str, Any] | None = None
    for row in enriched:
        if str(row.get("vt_symbol") or "").strip() == vt_symbol:
            target_row = dict(row)
            break
    if target_row is None:
        return {"error": f"未在行情池中找到: {vt_symbol}", "vt_symbol": vt_symbol}

    industry = str(target_row.get("industry") or "").strip()
    if not industry:
        return {
            "error": "缺少行业归属，无法做板块内龙头分层",
            "vt_symbol": vt_symbol,
            "name": str(target_row.get("name") or item.name or item.symbol),
        }

    limit_map = get_cached_limit_times_map()
    boards = resolve_limit_times(target_row, limit_times_map=limit_map)
    if boards >= 1:
        target_row["limit_times"] = boards

    peers = [dict(row) for row in enriched if str(row.get("industry") or "").strip() == industry]
    attach_first_time_fields(peers)

    group_ranking = rank_sector_group_full(
        peers,
        sector_name=industry,
        max_per_sector=_MAX_PER_SECTOR,
        include_breakdown=True,
    )
    target_entry = next((entry for entry in group_ranking if entry["vt_symbol"] == vt_symbol), None)
    if target_entry is None:
        return {"error": "板块内排序失败", "vt_symbol": vt_symbol, "sector": industry}

    tier = str(target_entry.get("leader_tier") or "")
    sector_rank = int(target_entry.get("sector_rank") or 0)
    leader_score = float(target_entry.get("leader_score") or 0)
    breakdown = dict(target_entry.get("score_breakdown") or {})
    peers_ahead = [entry for entry in group_ranking if int(entry.get("sector_rank") or 0) < sector_rank][:3]

    tiered_peers = rank_sector_leaders(peers, sector_key="industry", max_per_sector=_MAX_PER_SECTOR)
    sector_peers = [
        {
            "vt_symbol": str(scored.row.get("vt_symbol") or ""),
            "name": str(scored.row.get("name") or scored.row.get("symbol") or ""),
            "leader_tier": scored.leader_tier,
            "leader_tier_label": leader_tier_label(scored.leader_tier),
            "leader_score": scored.leader_score,
            "limit_times": int(scored.limit_times) if scored.limit_times >= 1 else 0,
        }
        for scored in tiered_peers[:5]
    ]

    key_drivers = _top_drivers(list(breakdown.get("components") or []))
    name = str(target_row.get("name") or item.name or item.symbol)
    summary = _build_summary(
        name=name,
        sector=industry,
        tier=tier,
        sector_rank=sector_rank,
        leader_score=leader_score,
        peers_ahead=peers_ahead,
        key_drivers=key_drivers,
    )
    reasons = _build_reasons(
        tier=tier,
        sector_rank=sector_rank,
        leader_score=leader_score,
        breakdown=breakdown,
        peers_ahead=peers_ahead,
    )

    return {
        "provider": "zak-leader-tier-v1",
        "vt_symbol": vt_symbol,
        "name": name,
        "sector": industry,
        "sector_axis": "industry",
        "leader_tier": tier,
        "leader_tier_label": leader_tier_label(tier) or "—",
        "sector_rank": sector_rank,
        "leader_score": leader_score,
        "limit_times": breakdown.get("limit_times"),
        "change_pct": target_row.get("change_pct"),
        "tier_rules": {
            "dragon_1": "板块内龙头分第 1",
            "dragon_2": "龙头分第 2",
            "follower": f"Top{_MAX_PER_SECTOR} 内且龙头分 ≥ {FOLLOWER_MIN_SCORE}",
        },
        "score_breakdown": breakdown,
        "key_drivers": key_drivers,
        "peers_ahead": peers_ahead,
        "sector_peers": sector_peers,
        "reasons": reasons,
        "summary": summary,
        "disclaimer": "规则计算结果，仅供研究，不构成买卖建议",
    }
