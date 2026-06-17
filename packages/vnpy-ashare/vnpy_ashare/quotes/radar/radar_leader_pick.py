"""选股·龙头卡片 loader 与候选池。"""

from __future__ import annotations

from typing import Any, Literal

from vnpy_ashare.quotes.radar.radar_catalog import RadarCardSpec
from vnpy_ashare.quotes.radar.radar_leader import LeaderScoredRow, leader_tier_label, rank_sector_leaders, score_market_leaders
from vnpy_ashare.quotes.radar.radar_models import RadarCardData, RadarRow, merge_row_quotes
from vnpy_ashare.quotes.radar.radar_sector import _row_from_leader_scored
from vnpy_ashare.screener.data.data_source import load_screening_quote_snapshot
from vnpy_ashare.screener.data.quotes_loader import MarketQuotesLoadError
from vnpy_ashare.screener.dimensions.sector_strength import run_sector_strength
from vnpy_ashare.screener.hard_filters import is_at_limit_board
from vnpy_ashare.screener.sector.sector_summary import attach_industry, compute_sector_distribution

LeaderPickVariant = Literal["mainline", "all_market"]

_STRONG_INDUSTRY_TOP = 5
_MIN_CHANGE_ALL_MARKET = 7.0


def build_leader_candidate_pool(
    *,
    variant: LeaderPickVariant = "mainline",
    pool_size: int = 80,
) -> tuple[list[dict[str, Any]], int]:
    """构建龙头评分候选池；返回 (candidates, total_scanned)。"""
    try:
        snapshot = load_screening_quote_snapshot()
    except MarketQuotesLoadError:
        return [], 0

    enriched = attach_industry(snapshot.rows)
    if not enriched:
        return [], snapshot.total

    if variant == "mainline":
        hits, _total = run_sector_strength(max(pool_size, 40), weight=1.0)
        return [merge_row_quotes(dict(hit.row)) for hit in hits], snapshot.total

    distribution = compute_sector_distribution(enriched, top_n=10, min_stocks=3)
    strong = {str(item["industry"]) for item in distribution[:_STRONG_INDUSTRY_TOP]}
    candidates: list[dict[str, Any]] = []
    for row in enriched:
        industry = str(row.get("industry") or "").strip()
        if not industry:
            continue
        merged = merge_row_quotes(row)
        change = float(merged.get("change_pct") or 0)
        if change < _MIN_CHANGE_ALL_MARKET and not is_at_limit_board(merged):
            continue
        merged["industry"] = industry
        if industry in strong:
            merged["sector_strength_bonus"] = 1.0
        candidates.append(merged)

    candidates.sort(
        key=lambda item: (
            float(item.get("change_pct") or 0),
            float(item.get("amount") or 0),
        ),
        reverse=True,
    )
    return candidates[:pool_size], snapshot.total


def rank_leader_pool(
    candidates: list[dict[str, Any]],
    *,
    top_n: int = 12,
    filter_followers: bool = False,
) -> list[LeaderScoredRow]:
    ranked = score_market_leaders(candidates, top_n=max(top_n * 2, top_n))
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
            empty_message="暂无龙头候选，请先同步行情与行业映射。",
            updated_at="",
            total_count=total,
        )

    ranked = rank_leader_pool(candidates, top_n=spec.top_n)
    rows: list[RadarRow] = []
    industries: list[str] = []
    for scored in ranked:
        parsed = _row_from_leader_scored(scored)
        if parsed is None:
            continue
        rows.append(parsed)
        industry = str(scored.row.get("industry") or "")
        if industry and industry not in industries:
            industries.append(industry)

    variant_label = "主线" if variant == "mainline" else "全市场"
    subtitle = f"{variant_label} · Top {len(rows)}"
    if industries:
        subtitle += " · " + "、".join(industries[:3])
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
        sector_names=tuple(industries[:6]),
    )
