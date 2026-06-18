"""雷达龙头选股执行。"""

from __future__ import annotations

from vnpy_ashare.domain.market.quote_row import quote_row_copy
from vnpy_ashare.domain.screener.result_row import ScreenerResultRow, update_screening_row
from vnpy_ashare.domain.time.china import format_china_datetime
from vnpy_ashare.quotes.market.emotion_cycle import load_emotion_cycle_snapshot
from vnpy_ashare.quotes.radar.radar_leader import LeaderScoredRow, leader_tier_label
from vnpy_ashare.quotes.radar.radar_leader_pick import (
    LeaderPickVariant,
    build_leader_candidate_pool,
    rank_leader_pool,
)
from vnpy_ashare.screener.enrich.regulatory import enrich_regulatory_tags
from vnpy_ashare.screener.hard_filters import apply_recipe_filters
from vnpy_ashare.screener.run.result import ScreenerRunResult, build_screener_run_result
from vnpy_ashare.screener.sector.sector_summary import attach_sector_fields, compute_sector_distribution
from vnpy_ashare.trading.signals.intraday_seal_time import attach_first_time_fields

_VARIANT_LABELS: dict[str, str] = {
    "mainline": "主线龙头",
    "all_market": "全市场龙头",
}


def leader_scored_to_result_row(scored: LeaderScoredRow) -> ScreenerResultRow:
    row = scored.row
    tier_label = leader_tier_label(scored.leader_tier)
    sector_name = scored.sector_name or str(row.get("industry") or row.get("concept") or "—")
    axis_label = "概念" if scored.sector_axis == "concept" else "行业"
    boards = int(scored.limit_times) if scored.limit_times >= 1 else 0
    board_text = f"{boards}板" if boards >= 1 else "—"
    enriched = quote_row_copy(
        row,
        symbol=str(row.symbol or row.vt_symbol.split(".")[0]),
        name=str(row.name or row.symbol or ""),
        last_price=float(row.last_price or row.close or 0),
        change_pct=float(row.change_pct or 0),
        leader_score=scored.leader_score,
        leader_tier=scored.leader_tier,
        leader_tier_label=tier_label,
        limit_times=boards if boards >= 1 else row.limit_times,
        sector_name=sector_name,
        sector_axis=scored.sector_axis or axis_label,
        hit_reason=(f"龙头 {tier_label} · {axis_label}{sector_name} · 评分 {scored.leader_score:.0f} · 连板 {board_text}"),
        source="radar_leader",
    )
    return ScreenerResultRow.from_mapping(enriched.to_dict())


def leader_scored_to_row(scored: LeaderScoredRow) -> dict:
    """兼容旧调用：返回 flat dict。"""
    return leader_scored_to_result_row(scored).to_dict()


def run_leader_screen(
    *,
    top_n: int = 12,
    variant: LeaderPickVariant = "mainline",
) -> ScreenerRunResult:
    """执行龙头选股：硬过滤 + 情绪周期 gate + leader_score 排序。"""
    top_n = max(1, min(int(top_n or 12), 200))
    cycle = load_emotion_cycle_snapshot(fetch_if_missing=True)
    variant_label = _VARIANT_LABELS.get(variant, variant)

    if cycle is not None and cycle.stage in {"recession", "ice"}:
        stage = cycle.stage_label
        return build_screener_run_result(
            rows=[],
            condition=f"雷达龙头（{stage}·不宜新开）",
            updated_at=format_china_datetime(),
            total_scanned=0,
            source="radar_leader",
        )

    candidates, total_scanned = build_leader_candidate_pool(
        variant=variant,
        pool_size=max(top_n * 8, 60),
    )
    if not candidates:
        raise RuntimeError("暂无全市场行情，请先采集 Redis 行情或打开市场页。")

    filtered = apply_recipe_filters([dict(row) for row in candidates])
    if not filtered:
        raise RuntimeError("硬过滤后无龙头候选，可调低过滤条件或刷新行情。")

    enriched, hot_concepts = attach_sector_fields(filtered)
    pool = enriched or filtered
    industry_distribution = compute_sector_distribution(pool, top_n=8, min_stocks=3)
    concept_distribution = compute_sector_distribution(pool, top_n=8, min_stocks=3, sector_field="concept")
    strong_industries = {str(item["industry"]) for item in industry_distribution[:5]}
    strong_concepts = {str(item["concept"]) for item in concept_distribution[:5]} | set(hot_concepts)

    filter_followers = cycle is not None and cycle.stage == "divergence"
    pool_rows = [dict(row) for row in pool]
    attach_first_time_fields(pool_rows)
    ranked = rank_leader_pool(
        pool_rows,
        top_n=top_n,
        filter_followers=filter_followers,
        strong_industries=strong_industries,
        strong_concepts=strong_concepts,
    )
    rows = [leader_scored_to_result_row(item) for item in ranked]
    for index, item in enumerate(ranked):
        label = str(item.row.get("seal_reopen_label") or "").strip()
        if label:
            rows[index] = update_screening_row(rows[index], seal_reopen_label=label)
    rows = enrich_regulatory_tags(rows)

    condition = f"雷达龙头 · {variant_label}"
    if cycle is not None:
        condition += f" · {cycle.stage_label}"

    return build_screener_run_result(
        rows=rows,
        condition=condition,
        updated_at=format_china_datetime(),
        total_scanned=total_scanned,
        source="radar_leader",
    )
