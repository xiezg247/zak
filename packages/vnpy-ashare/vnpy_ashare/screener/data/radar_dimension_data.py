"""雷达维度共用数据：龙头评分池、共振行。"""

from __future__ import annotations

from typing import Any

import polars as pl

from vnpy_ashare.domain.market.quote_row import quote_row_to_dict
from vnpy_ashare.integrations.tushare.concept_board import build_hot_concept_vt_symbol_map
from vnpy_ashare.quotes.market.emotion_cycle import load_emotion_cycle_snapshot
from vnpy_ashare.quotes.radar.radar_board_store import get_radar_board_snapshot
from vnpy_ashare.quotes.radar.radar_leader_pick import build_leader_candidate_pool, rank_leader_pool
from vnpy_ashare.quotes.radar.radar_resonance_store import get_radar_resonance_entries
from vnpy_ashare.screener.data.data_source import load_screening_quote_snapshot
from vnpy_ashare.screener.data.quotes_loader import MarketQuotesLoadError
from vnpy_ashare.screener.engine.dimensions.radar_resonance import build_radar_resonance_rows_polars
from vnpy_ashare.screener.engine.sector_stats import compute_sector_distribution_polars
from vnpy_ashare.screener.engine.snapshot_frame import snapshot_rows_to_dataframe
from vnpy_ashare.screener.sector.sector_summary import attach_sector_fields

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


def _strong_sectors_for_leader_pool(pool: list[Any], hot_concepts: list[str]) -> tuple[set[str], set[str]]:
    df = snapshot_rows_to_dataframe(pool)
    if df.is_empty():
        return set(), set(hot_concepts)
    industry_dist = compute_sector_distribution_polars(df, top_n=8, min_stocks=3)
    strong_industries = (
        {str(value) for value in industry_dist.head(5)["industry"].to_list()} if not industry_dist.is_empty() else set()
    )
    vt_to_concept, _hot = build_hot_concept_vt_symbol_map()
    strong_concepts: set[str] = set()
    if vt_to_concept:
        map_df = pl.DataFrame(
            {"vt_symbol": list(vt_to_concept.keys()), "concept": list(vt_to_concept.values())},
        )
        concept_df = df.join(map_df, on="vt_symbol", how="inner")
        concept_dist = compute_sector_distribution_polars(concept_df, top_n=8, min_stocks=3, sector_col="concept")
        if not concept_dist.is_empty():
            strong_concepts = {str(value) for value in concept_dist.head(5)["industry"].to_list()}
    return strong_industries, strong_concepts | set(hot_concepts)


def build_leader_score_dimension_rows(pool_size: int) -> tuple[list[dict[str, Any]], int]:
    """主线龙头候选 → 带 leader_score / leader_tier 的行情行。"""
    candidates, total = build_leader_candidate_pool(variant="mainline", pool_size=max(pool_size * 2, 60))
    if not candidates:
        return [], total

    enriched, hot_concepts = attach_sector_fields(candidates)
    pool = enriched or candidates
    strong_industries, strong_concepts = _strong_sectors_for_leader_pool(pool, hot_concepts)

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

    rows = build_radar_resonance_rows_polars(entries, list(snapshot.rows), pool_size=pool_size)
    return rows, snapshot.total
