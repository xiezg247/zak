"""龙头评分与板块内分层（G-04）。"""

from __future__ import annotations

from typing import Any

from vnpy_ashare.domain.market.quote_row import QuoteRow, QuoteRowLike, QuoteRowsLike, coerce_quote_row
from vnpy_ashare.domain.radar.leader import LeaderScoredRow, LeaderTier
from vnpy_ashare.quotes.radar.radar_leader_score import (
    FOLLOWER_MIN_SCORE,
    batch_leader_parts_polars,
    board_quality_score,
    clamp01,
    compute_leader_score,
    compute_leader_score_breakdown,
    leader_score_weights_for_stage,
    seal_quality_proxy,
)
from vnpy_ashare.screener.hard_filters import is_at_limit_board
from vnpy_ashare.trading.signals.seal_time import seal_time_score

__all__ = [
    "LeaderScoredRow",
    "LeaderTier",
    "FOLLOWER_MIN_SCORE",
    "board_quality_score",
    "compute_leader_score",
    "compute_leader_score_breakdown",
    "leader_score_weights_for_stage",
    "leader_tier_label",
    "rank_sector_group_full",
    "rank_sector_leaders",
    "rank_unified_sector_leaders",
    "score_market_leaders",
    "seal_quality_proxy",
    "tier_for_group_rank",
]

_TIER_LABELS: dict[str, str] = {
    "dragon_1": "龙一",
    "dragon_2": "龙二",
    "follower": "跟风",
}


def leader_tier_label(tier: str) -> str:
    return _TIER_LABELS.get(tier, "")


def tier_for_group_rank(index: int, *, leader_score: float, max_per_sector: int = 5) -> LeaderTier:
    """板块内排序序号 → 龙头分层（与 rank_sector_leaders 规则一致）。"""
    if index == 0:
        return "dragon_1"
    if index == 1:
        return "dragon_2"
    if index < max_per_sector and leader_score >= FOLLOWER_MIN_SCORE:
        return "follower"
    return ""


def rank_sector_group_full(
    group_rows: QuoteRowsLike,
    *,
    sector_name: str = "",
    sector_key: str = "industry",
    max_per_sector: int = 8,
    strong_sectors: set[str] | None = None,
    include_breakdown: bool = False,
    emotion_stage: str | None = None,
) -> list[dict[str, Any]]:
    """单板块候选全量排序；可选返回 score_breakdown（供 explain_leader_tier）。"""
    if not group_rows:
        return []

    weights = leader_score_weights_for_stage(emotion_stage)
    max_mf = max(abs(float(row.get("net_mf_amount") or 0)) for row in group_rows)
    bonus = 1.0
    if strong_sectors is not None and sector_name:
        bonus = 1.0 if sector_name in strong_sectors else 0.55

    batch_parts = batch_leader_parts_polars(
        group_rows, max_net_mf=max_mf, sector_strength_bonus=bonus,
    )

    scored: list[tuple[QuoteRow, float, float]] = []
    for idx, row in enumerate(group_rows):
        coerced = coerce_quote_row(row)
        parts = batch_parts[idx]
        parts["seal_quality"] = seal_quality_proxy(coerced)
        parts["seal_time"] = clamp01(
            float(coerced.get("seal_time_score") or seal_time_score(str(coerced.get("first_time") or "")))
        )
        score = sum(parts.get(key, 0) * weights.get(key, 0) for key in weights) * 100.0
        leader_score = round(max(0.0, min(100.0, score)), 1)
        boards = float(coerced.get("limit_times") or 0)
        if boards < 1 and is_at_limit_board(coerced):
            boards = 1.0
        scored.append((coerced, leader_score, boards))

    scored.sort(
        key=lambda item: (item[1], item[2], float(item[0].get("change_pct") or 0)),
        reverse=True,
    )

    results: list[dict[str, Any]] = []
    for index, (row, score, boards) in enumerate(scored):
        tier = tier_for_group_rank(index, leader_score=score, max_per_sector=max_per_sector)
        vt = str(row.get("vt_symbol") or "")
        entry: dict[str, Any] = {
            "vt_symbol": vt,
            "name": str(row.get("name") or row.get("symbol") or vt),
            "sector_rank": index + 1,
            "leader_score": score,
            "leader_tier": tier,
            "leader_tier_label": leader_tier_label(tier),
            "limit_times": int(boards) if boards >= 1 else 0,
            "change_pct": row.get("change_pct"),
            "in_tier_pool": index < max_per_sector,
            "sector_axis": sector_key,
            "sector_name": sector_name,
        }
        if include_breakdown:
            entry["score_breakdown"] = compute_leader_score_breakdown(
                row,
                amount_rank=batch_parts[index].get("_amount_rank", 0.5),
                sector_strength_bonus=bonus,
                max_net_mf=max_mf,
                emotion_stage=emotion_stage,
            )
        results.append(entry)
    return results


def rank_sector_leaders(
    candidates: QuoteRowsLike,
    *,
    sector_key: str = "industry",
    max_per_sector: int = 5,
    strong_sectors: set[str] | None = None,
    emotion_stage: str | None = None,
) -> list[LeaderScoredRow]:
    """同板块内降序；Top1=龙一，Top2=龙二，其余强势=跟风。"""
    if not candidates:
        return []

    grouped: dict[str, list[QuoteRow]] = {}
    for row in candidates:
        key = str(row.get(sector_key) or "—")
        if key == "—":
            continue
        grouped.setdefault(key, []).append(coerce_quote_row(row))

    weights = leader_score_weights_for_stage(emotion_stage)
    ranked: list[LeaderScoredRow] = []
    for group_name, group_rows in grouped.items():
        bonus = 1.0 if (strong_sectors is None or group_name in strong_sectors) else 0.55
        max_mf = max(abs(float(row.get("net_mf_amount") or 0)) for row in group_rows)
        batch_parts = batch_leader_parts_polars(
            group_rows, max_net_mf=max_mf, sector_strength_bonus=bonus,
        )

        scored: list[tuple[QuoteRow, float, float]] = []
        for idx, row in enumerate(group_rows):
            parts = batch_parts[idx]
            parts["seal_quality"] = seal_quality_proxy(row)
            parts["seal_time"] = clamp01(
                float(row.get("seal_time_score") or seal_time_score(str(row.get("first_time") or "")))
            )
            score = sum(parts.get(key, 0) * weights.get(key, 0) for key in weights) * 100.0
            leader_score = round(max(0.0, min(100.0, score)), 1)
            boards = float(row.get("limit_times") or 0)
            if boards < 1 and is_at_limit_board(row):
                boards = 1.0
            scored.append((row, leader_score, boards))

        scored.sort(key=lambda item: (item[1], item[2], float(item[0].get("change_pct") or 0)), reverse=True)

        for index, (row, score, boards) in enumerate(scored[:max_per_sector]):
            tier = tier_for_group_rank(index, leader_score=score, max_per_sector=max_per_sector)
            if tier:
                ranked.append(
                    LeaderScoredRow(
                        row=row,
                        leader_score=score,
                        leader_tier=tier,
                        limit_times=boards,
                        sector_axis=sector_key,
                        sector_name=group_name,
                    )
                )

    ranked.sort(
        key=lambda item: (
            {"dragon_1": 3, "dragon_2": 2, "follower": 1}.get(item.leader_tier, 0),
            item.leader_score,
            float(item.row.get("change_pct") or 0),
        ),
        reverse=True,
    )
    return ranked


_TIER_PRIORITY = {"dragon_1": 3, "dragon_2": 2, "follower": 1, "": 0}


def _pick_better_leader(a: LeaderScoredRow, b: LeaderScoredRow) -> LeaderScoredRow:
    pa = _TIER_PRIORITY.get(a.leader_tier, 0)
    pb = _TIER_PRIORITY.get(b.leader_tier, 0)
    if pa != pb:
        return a if pa > pb else b
    if a.leader_score != b.leader_score:
        return a if a.leader_score > b.leader_score else b
    if a.limit_times != b.limit_times:
        return a if a.limit_times > b.limit_times else b
    return a


def rank_unified_sector_leaders(
    candidates: QuoteRowsLike,
    *,
    max_per_sector: int = 5,
    strong_industries: set[str] | None = None,
    strong_concepts: set[str] | None = None,
    emotion_stage: str | None = None,
) -> list[LeaderScoredRow]:
    """行业 + 概念双轴统一 scoring；每票取更强分层结果（G-07）。"""
    industry_rows = [row for row in candidates if str(row.get("industry") or "").strip()]
    concept_rows = [row for row in candidates if str(row.get("concept") or "").strip()]

    by_vt: dict[str, LeaderScoredRow] = {}
    for axis, rows, strong in (
        ("industry", industry_rows, strong_industries),
        ("concept", concept_rows, strong_concepts),
    ):
        if not rows:
            continue
        for scored in rank_sector_leaders(
            rows,
            sector_key=axis,
            max_per_sector=max_per_sector,
            strong_sectors=strong,
            emotion_stage=emotion_stage,
        ):
            vt = str(scored.row.get("vt_symbol") or "")
            if not vt:
                continue
            existing = by_vt.get(vt)
            if existing is None:
                by_vt[vt] = scored
            else:
                by_vt[vt] = _pick_better_leader(existing, scored)

    merged = list(by_vt.values())
    merged.sort(
        key=lambda item: (
            _TIER_PRIORITY.get(item.leader_tier, 0),
            item.leader_score,
            float(item.row.get("change_pct") or 0),
        ),
        reverse=True,
    )
    return merged


def score_market_leaders(
    candidates: QuoteRowsLike,
    *,
    top_n: int = 12,
    strong_industries: set[str] | None = None,
    strong_concepts: set[str] | None = None,
    emotion_stage: str | None = None,
) -> list[LeaderScoredRow]:
    """全市场候选 → 行业/概念双轴分层 → 按龙头分取 Top N。"""
    ranked = rank_unified_sector_leaders(
        candidates,
        strong_industries=strong_industries,
        strong_concepts=strong_concepts,
        emotion_stage=emotion_stage,
    )
    return ranked[: max(1, top_n)]
