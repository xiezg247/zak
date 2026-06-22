"""雷达维度共用数据：龙头评分池、共振行。"""

from __future__ import annotations

from typing import Any

from vnpy_ashare.domain.market.quote_row import quote_row_to_dict
from vnpy_ashare.quotes.market.emotion_cycle import load_emotion_cycle_snapshot
from vnpy_ashare.quotes.radar.radar_board_store import get_radar_board_snapshot
from vnpy_ashare.quotes.radar.radar_leader_pick import build_leader_candidate_pool, rank_leader_pool
from vnpy_ashare.quotes.radar.radar_resonance_store import get_radar_resonance_entries
from vnpy_ashare.screener.data.data_source import load_screening_quote_snapshot
from vnpy_ashare.screener.data.quotes_loader import MarketQuotesLoadError
from vnpy_ashare.screener.sector.sector_summary import attach_sector_fields, compute_sector_distribution

__all__ = [
    "build_leader_score_dimension_rows",
    "build_radar_resonance_dimension_rows",
    "resonance_entries_for_dimension",
]


def resonance_entries_for_dimension() -> tuple:
    snapshot = get_radar_board_snapshot()
    if snapshot is not None and snapshot.resonance_entries:
        return snapshot.resonance_entries
    return get_radar_resonance_entries()


def build_leader_score_dimension_rows(pool_size: int) -> tuple[list[dict[str, Any]], int]:
    """主线龙头候选 → 带 leader_score / leader_tier 的行情行。"""
    candidates, total = build_leader_candidate_pool(variant="mainline", pool_size=max(pool_size * 2, 60))
    if not candidates:
        return [], total

    enriched, hot_concepts = attach_sector_fields(candidates)
    pool = enriched or candidates
    industry_distribution = compute_sector_distribution(pool, top_n=8, min_stocks=3)
    concept_distribution = compute_sector_distribution(pool, top_n=8, min_stocks=3, sector_field="concept")
    strong_industries = {str(item["industry"]) for item in industry_distribution[:5]}
    strong_concepts = {str(item["concept"]) for item in concept_distribution[:5]} | set(hot_concepts)

    cycle = load_emotion_cycle_snapshot(fetch_if_missing=False)
    ranked = rank_leader_pool(
        pool,
        top_n=pool_size,
        strong_industries=strong_industries,
        strong_concepts=strong_concepts,
        emotion_stage=cycle.stage if cycle is not None else None,
    )

    rows: list[dict[str, Any]] = []
    for item in ranked:
        payload = quote_row_to_dict(item.row)
        payload["leader_score"] = item.leader_score
        payload["leader_tier"] = item.leader_tier
        payload["limit_times"] = int(item.limit_times) if item.limit_times >= 1 else 0
        rows.append(payload)
    return rows, total


def build_radar_resonance_dimension_rows(pool_size: int) -> tuple[list[dict[str, Any]], int]:
    """共振≥2卡标的，合并行情并附 resonance_score。"""
    entries = [entry for entry in resonance_entries_for_dimension() if entry.card_count >= 2]
    if not entries:
        return [], 0

    try:
        snapshot = load_screening_quote_snapshot()
    except MarketQuotesLoadError:
        return [], 0

    by_vt = {str(row.get("vt_symbol") or ""): row for row in snapshot.rows}
    rows: list[dict[str, Any]] = []
    for entry in entries:
        raw = by_vt.get(entry.vt_symbol)
        if raw is None:
            continue
        payload = dict(raw)
        payload["resonance_score"] = entry.resonance_score
        payload["resonance_card_count"] = entry.card_count
        if entry.leader_tier:
            payload["leader_tier"] = entry.leader_tier
        if entry.leader_score is not None:
            payload["leader_score"] = entry.leader_score
        rows.append(payload)

    rows.sort(
        key=lambda row: (
            float(row.get("resonance_score") or 0),
            float(row.get("resonance_card_count") or 0),
        ),
        reverse=True,
    )
    return rows[:pool_size], snapshot.total
