"""选股·龙头卡片 loader 与候选池。"""

from __future__ import annotations

from typing import Any, Literal

from vnpy_ashare.domain.market.quote_row import QuoteRow, QuoteRowsLike, quote_row_copy
from vnpy_ashare.quotes.market.emotion_cycle import load_emotion_cycle_snapshot
from vnpy_ashare.quotes.radar.radar_catalog import RadarCardSpec
from vnpy_ashare.quotes.radar.radar_leader import LeaderScoredRow, score_market_leaders
from vnpy_ashare.quotes.radar.radar_models import RadarCardData, RadarRow, merge_row_quotes
from vnpy_ashare.quotes.radar.radar_sector import _row_from_leader_scored
from vnpy_ashare.screener.data.data_source import load_screening_quote_snapshot
from vnpy_ashare.screener.data.quotes_loader import MarketQuotesLoadError
from vnpy_ashare.screener.dimensions.sector_strength import run_sector_strength
from vnpy_ashare.screener.hard_filters import is_at_limit_board
from vnpy_ashare.screener.sector.sector_summary import attach_sector_fields, compute_sector_distribution
from vnpy_ashare.trading.signals.intraday_seal_time import attach_first_time_fields

LeaderPickVariant = Literal["mainline", "all_market"]

_STRONG_INDUSTRY_TOP = 5
_MIN_CHANGE_ALL_MARKET = 7.0


def build_leader_candidate_pool(
    *,
    variant: LeaderPickVariant = "mainline",
    pool_size: int = 80,
) -> tuple[list[QuoteRow | dict[str, Any]], int]:
    """构建龙头评分候选池；返回 (candidates, total_scanned)。"""
    try:
        snapshot = load_screening_quote_snapshot()
    except MarketQuotesLoadError:
        return [], 0

    enriched, hot_concepts = attach_sector_fields(snapshot.rows)
    if not enriched:
        return [], snapshot.total

    if variant == "mainline":
        hits, _total = run_sector_strength(max(pool_size, 40), weight=1.0)
        hit_rows = [merge_row_quotes(hit.row) for hit in hits]
        enriched_hits, hot_concepts = attach_sector_fields(hit_rows)
        pool_rows: list[QuoteRow | dict[str, Any]] = []
        for row in enriched_hits or hit_rows:
            vt = str(row.get("vt_symbol") or "")
            if vt:
                pool_rows.append(quote_row_copy(row, sector_strength_bonus=1.0))
            else:
                pool_rows.append(row)
        attach_first_time_fields(pool_rows)
        return pool_rows, snapshot.total

    distribution = compute_sector_distribution(enriched, top_n=10, min_stocks=3)
    concept_distribution = compute_sector_distribution(enriched, top_n=10, min_stocks=3, sector_field="concept")
    strong = {str(item["industry"]) for item in distribution[:_STRONG_INDUSTRY_TOP]}
    strong_concepts = {str(item["concept"]) for item in concept_distribution[:_STRONG_INDUSTRY_TOP]}
    strong |= set(hot_concepts)
    candidates: list[QuoteRow | dict[str, Any]] = []
    for row in enriched:
        industry = str(row.get("industry") or "").strip()
        concept = str(row.get("concept") or "").strip()
        if not industry and not concept:
            continue
        merged = merge_row_quotes(row)
        change = float(merged.get("change_pct") or 0)
        if change < _MIN_CHANGE_ALL_MARKET and not is_at_limit_board(merged):
            continue
        if industry:
            merged["industry"] = industry
        if concept:
            merged["concept"] = concept
        if industry in strong or concept in strong_concepts or concept in hot_concepts:
            merged["sector_strength_bonus"] = 1.0
        candidates.append(merged)

    candidates.sort(
        key=lambda item: (
            float(item.get("change_pct") or 0),
            float(item.get("amount") or 0),
        ),
        reverse=True,
    )
    trimmed = candidates[:pool_size]
    attach_first_time_fields(trimmed)
    return trimmed, snapshot.total


def rank_leader_pool(
    candidates: QuoteRowsLike,
    *,
    top_n: int = 12,
    filter_followers: bool = False,
    strong_industries: set[str] | None = None,
    strong_concepts: set[str] | None = None,
    emotion_stage: str | None = None,
) -> list[LeaderScoredRow]:
    ranked = score_market_leaders(
        candidates,
        top_n=max(top_n * 2, top_n),
        strong_industries=strong_industries,
        strong_concepts=strong_concepts,
        emotion_stage=emotion_stage,
    )
    if filter_followers:
        ranked = [item for item in ranked if item.leader_tier in {"dragon_1", "dragon_2"}]
    return ranked[:top_n]


def load_leader_pick(spec: RadarCardSpec, *, variant: LeaderPickVariant = "mainline") -> RadarCardData:
    candidates, total = build_leader_candidate_pool(variant=variant, pool_size=max(spec.top_n * 6, 40))
    if not candidates:
        return RadarCardData(
            card_id=spec.id,
            title=spec.title,
            subtitle="",
            rows=(),
            empty_message="暂无龙头候选，请先同步行情与行业/概念映射。",
            updated_at="",
            total_count=total,
        )

    enriched, hot_concepts = attach_sector_fields(candidates)
    pool = enriched or candidates
    industry_distribution = compute_sector_distribution(pool, top_n=8, min_stocks=3)
    concept_distribution = compute_sector_distribution(pool, top_n=8, min_stocks=3, sector_field="concept")
    strong_industries = {str(item["industry"]) for item in industry_distribution[:5]}
    strong_concepts = {str(item["concept"]) for item in concept_distribution[:5]} | set(hot_concepts)

    cycle = load_emotion_cycle_snapshot(fetch_if_missing=False)
    emotion_stage = cycle.stage if cycle is not None else None

    ranked = rank_leader_pool(
        pool,
        top_n=spec.top_n,
        strong_industries=strong_industries,
        strong_concepts=strong_concepts,
        emotion_stage=emotion_stage,
    )
    rows: list[RadarRow] = []
    sector_names: list[str] = []
    for scored in ranked:
        parsed = _row_from_leader_scored(scored)
        if parsed is None:
            continue
        rows.append(parsed)
        sector = scored.sector_name or str(scored.row.get("industry") or scored.row.get("concept") or "")
        if sector and sector not in sector_names:
            sector_names.append(sector)

    variant_label = "主线" if variant == "mainline" else "全市场"
    subtitle = f"{variant_label} · Top {len(rows)}"
    if sector_names:
        subtitle += " · " + "、".join(sector_names[:3])
    if hot_concepts:
        subtitle += " · 概念" + "、".join(hot_concepts[:2])
    if total:
        subtitle += f" · 扫描 {total} 只"

    return RadarCardData(
        card_id=spec.id,
        title=spec.title,
        subtitle=subtitle,
        rows=tuple(rows),
        empty_message="",
        updated_at="",
        total_count=len(rows),
        sector_names=tuple(sector_names[:6]),
    )
