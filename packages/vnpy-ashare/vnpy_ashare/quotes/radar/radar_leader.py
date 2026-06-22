"""龙头评分与板块内分层（G-04）。"""

from __future__ import annotations

from typing import Any, cast

from vnpy_ashare.domain.market.emotion import EmotionStage
from vnpy_ashare.domain.market.quote_row import QuoteRow, QuoteRowLike, QuoteRowsLike, coerce_quote_row, quote_row_to_dict
from vnpy_ashare.domain.radar.leader import LeaderScoredRow, LeaderTier
from vnpy_ashare.quotes.market.market_breadth import LIMIT_UP_PCT
from vnpy_ashare.screener.hard_filters import is_at_limit_board
from vnpy_ashare.trading.signals.seal_reopen import seal_reopen_from_row
from vnpy_ashare.trading.signals.seal_strength import seal_strength_from_row
from vnpy_ashare.trading.signals.seal_time import seal_time_score

__all__ = [
    "LeaderScoredRow",
    "LeaderTier",
    "FOLLOWER_MIN_SCORE",
    "compute_leader_score",
    "compute_leader_score_breakdown",
    "leader_score_weights_for_stage",
    "leader_tier_label",
    "rank_sector_group_full",
    "rank_sector_leaders",
    "rank_unified_sector_leaders",
    "score_market_leaders",
    "tier_for_group_rank",
]

_TIER_LABELS: dict[str, str] = {
    "dragon_1": "龙一",
    "dragon_2": "龙二",
    "follower": "跟风",
}

_DEFAULT_WEIGHTS: dict[str, float] = {
    "limit_times": 0.28,
    "seal_quality": 0.18,
    "amount_rank": 0.15,
    "seal_time": 0.12,
    "net_mf": 0.12,
    "sector_strength": 0.10,
    "resonance": 0.05,
}

_FOLLOWER_MIN_SCORE = 35.0
FOLLOWER_MIN_SCORE = _FOLLOWER_MIN_SCORE

_STAGE_WEIGHT_MULTIPLIERS: dict[EmotionStage, dict[str, float]] = {
    "startup": {
        "seal_time": 1.35,
        "sector_strength": 1.25,
        "limit_times": 0.85,
    },
    "climax": {
        "limit_times": 1.25,
        "seal_quality": 1.15,
        "amount_rank": 1.1,
    },
    "divergence": {
        "seal_quality": 1.2,
        "net_mf": 1.15,
        "limit_times": 0.9,
    },
}


def leader_score_weights_for_stage(stage: str | None) -> dict[str, float]:
    """情绪阶段自适应权重（归一化后与默认维度键一致）。"""
    base = dict(_DEFAULT_WEIGHTS)
    if not stage:
        return base
    multipliers = _STAGE_WEIGHT_MULTIPLIERS.get(cast(EmotionStage, stage))
    if not multipliers:
        return base
    adjusted = {key: base[key] * multipliers.get(key, 1.0) for key in base}
    total = sum(adjusted.values())
    if total <= 0:
        return base
    return {key: round(value / total, 4) for key, value in adjusted.items()}


_COMPONENT_LABELS: dict[str, str] = {
    "limit_times": "连板高度",
    "seal_quality": "封板质量",
    "amount_rank": "成交额排名",
    "seal_time": "封板时间",
    "net_mf": "主力净流入",
    "sector_strength": "板块强度",
    "resonance": "共振加成",
}


def leader_tier_label(tier: str) -> str:
    return _TIER_LABELS.get(tier, "")


def tier_for_group_rank(index: int, *, leader_score: float, max_per_sector: int = 5) -> LeaderTier:
    """板块内排序序号 → 龙头分层（与 rank_sector_leaders 规则一致）。"""
    if index == 0:
        return "dragon_1"
    if index == 1:
        return "dragon_2"
    if index < max_per_sector and leader_score >= _FOLLOWER_MIN_SCORE:
        return "follower"
    return ""


def _leader_score_parts(
    row: QuoteRowLike,
    *,
    amount_rank: float = 0.5,
    sector_strength_bonus: float = 1.0,
    resonance_bonus: float = 0.0,
    max_net_mf: float = 0.0,
) -> tuple[dict[str, float], float]:
    limit_times = float(row.get("limit_times") or 0)
    if limit_times < 1 and is_at_limit_board(row):
        limit_times = 1.0
    parts = {
        "limit_times": _norm_limit_times(limit_times),
        "seal_quality": _seal_quality_proxy(row),
        "amount_rank": _clamp01(amount_rank),
        "seal_time": _clamp01(float(row.get("seal_time_score") or seal_time_score(str(row.get("first_time") or "")))),
        "net_mf": _norm_net_mf(row, max_abs=max_net_mf),
        "sector_strength": _clamp01(sector_strength_bonus),
        "resonance": _clamp01(resonance_bonus),
    }
    return parts, limit_times


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _norm_limit_times(limit_times: float) -> float:
    boards = max(0.0, limit_times)
    if boards <= 0:
        return 0.2
    return _clamp01(boards / 5.0)


def _seal_quality_proxy(row: QuoteRowLike) -> float:
    """封板质量：封单强度 + 炸板回封，否则成交额代理。"""
    strength = seal_strength_from_row(quote_row_to_dict(row))
    _kind, _label, reopen_score, _times = seal_reopen_from_row(row)

    parts: list[float] = []
    if strength > 0:
        parts.append(strength)
    if reopen_score > 0:
        parts.append(reopen_score)
    if parts:
        return round(sum(parts) / len(parts), 4)

    change = float(row.get("change_pct") or 0)
    if not is_at_limit_board(row):
        return _clamp01(change / max(LIMIT_UP_PCT, 1.0) * 0.6)

    amplitude = float(row.get("amplitude") or row.get("swing") or 0)
    if amplitude > 0 and amplitude < 0.5:
        return 0.25
    amount = float(row.get("amount") or 0)
    if amount >= 5e8:
        return 1.0
    if amount >= 1e8:
        return 0.75
    if amount >= 5e7:
        return 0.55
    return 0.4


def _norm_net_mf(row: QuoteRowLike, *, max_abs: float) -> float:
    raw = float(row.get("net_mf_amount") or 0)
    if max_abs <= 0:
        return 0.5 if raw > 0 else 0.0
    if raw <= 0:
        return 0.0
    return _clamp01(raw / max_abs)


def _amount_rank_in_group(rows: QuoteRowsLike) -> dict[str, float]:
    amounts = [(str(row.get("vt_symbol") or ""), float(row.get("amount") or 0)) for row in rows]
    amounts = [(vt, amt) for vt, amt in amounts if vt]
    if not amounts:
        return {}
    sorted_amounts = sorted(amount for _, amount in amounts)
    n = len(sorted_amounts)
    result: dict[str, float] = {}
    for vt, amount in amounts:
        if amount <= 0:
            result[vt] = 0.0
            continue
        rank = sum(1 for value in sorted_amounts if value <= amount)
        result[vt] = _clamp01(rank / n)
    return result


def compute_leader_score(
    row: QuoteRowLike,
    *,
    amount_rank: float = 0.5,
    sector_strength_bonus: float = 1.0,
    resonance_bonus: float = 0.0,
    max_net_mf: float = 0.0,
    weights: dict[str, float] | None = None,
    emotion_stage: str | None = None,
) -> float:
    return cast(
        float,
        compute_leader_score_breakdown(
            row,
            amount_rank=amount_rank,
            sector_strength_bonus=sector_strength_bonus,
            resonance_bonus=resonance_bonus,
            max_net_mf=max_net_mf,
            weights=weights,
            emotion_stage=emotion_stage,
        )["leader_score"],
    )


def compute_leader_score_breakdown(
    row: QuoteRowLike,
    *,
    amount_rank: float = 0.5,
    sector_strength_bonus: float = 1.0,
    resonance_bonus: float = 0.0,
    max_net_mf: float = 0.0,
    weights: dict[str, float] | None = None,
    emotion_stage: str | None = None,
) -> dict[str, object]:
    """龙头分及加权分项（供 explain_leader_tier 等解读）。"""
    w = leader_score_weights_for_stage(emotion_stage) if weights is None else dict(_DEFAULT_WEIGHTS)
    if weights:
        w.update(weights)

    parts, limit_times = _leader_score_parts(
        row,
        amount_rank=amount_rank,
        sector_strength_bonus=sector_strength_bonus,
        resonance_bonus=resonance_bonus,
        max_net_mf=max_net_mf,
    )
    score = sum(parts[key] * w[key] for key in w) * 100.0
    leader_score = round(max(0.0, min(100.0, score)), 1)
    components = [
        {
            "key": key,
            "label": _COMPONENT_LABELS[key],
            "norm": round(parts[key], 4),
            "weight": w[key],
            "points": round(parts[key] * w[key] * 100.0, 1),
        }
        for key in w
    ]
    return {
        "leader_score": leader_score,
        "limit_times": int(limit_times) if limit_times >= 1 else 0,
        "components": components,
        "weights_note": "与 radar_leader.compute_leader_score 默认权重一致",
    }


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

    amount_ranks = _amount_rank_in_group(group_rows)
    max_mf = max(abs(float(row.get("net_mf_amount") or 0)) for row in group_rows)
    bonus = 1.0
    if strong_sectors is not None and sector_name:
        bonus = 1.0 if sector_name in strong_sectors else 0.55

    scored: list[tuple[QuoteRow, float, float]] = []
    for row in group_rows:
        coerced = coerce_quote_row(row)
        vt = str(coerced.get("vt_symbol") or "")
        score = compute_leader_score(
            coerced,
            amount_rank=amount_ranks.get(vt, 0.5),
            sector_strength_bonus=bonus,
            max_net_mf=max_mf,
            emotion_stage=emotion_stage,
        )
        boards = float(coerced.get("limit_times") or 0)
        if boards < 1 and is_at_limit_board(coerced):
            boards = 1.0
        scored.append((coerced, score, boards))

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
                amount_rank=amount_ranks.get(vt, 0.5),
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

    ranked: list[LeaderScoredRow] = []
    for group_name, group_rows in grouped.items():
        amount_ranks = _amount_rank_in_group(group_rows)
        max_mf = max(abs(float(row.get("net_mf_amount") or 0)) for row in group_rows)
        scored: list[tuple[QuoteRow, float, float]] = []
        for row in group_rows:
            vt = str(row.get("vt_symbol") or "")
            bonus = 1.0
            if strong_sectors is not None:
                bonus = 1.0 if group_name in strong_sectors else 0.55
            score = compute_leader_score(
                row,
                amount_rank=amount_ranks.get(vt, 0.5),
                sector_strength_bonus=bonus,
                max_net_mf=max_mf,
                emotion_stage=emotion_stage,
            )
            boards = float(row.get("limit_times") or 0)
            if boards < 1 and is_at_limit_board(row):
                boards = 1.0
            scored.append((row, score, boards))
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
