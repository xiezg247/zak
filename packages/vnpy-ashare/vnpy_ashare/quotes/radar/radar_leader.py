"""龙头评分与板块内分层（G-04）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from vnpy_ashare.quotes.market.market_breadth import LIMIT_UP_PCT
from vnpy_ashare.screener.hard_filters import is_at_limit_board

LeaderTier = Literal["dragon_1", "dragon_2", "follower", ""]

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


@dataclass(frozen=True)
class LeaderScoredRow:
    row: dict[str, Any]
    leader_score: float
    leader_tier: LeaderTier
    limit_times: float


def leader_tier_label(tier: str) -> str:
    return _TIER_LABELS.get(tier, "")


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _norm_limit_times(limit_times: float) -> float:
    boards = max(0.0, limit_times)
    if boards <= 0:
        return 0.2
    return _clamp01(boards / 5.0)


def _seal_quality_proxy(row: dict[str, Any]) -> float:
    """Phase 1：涨停 + 非近似一字 + 成交额分位代理。"""
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


def _norm_net_mf(row: dict[str, Any], *, max_abs: float) -> float:
    raw = float(row.get("net_mf_amount") or 0)
    if max_abs <= 0:
        return 0.5 if raw > 0 else 0.0
    if raw <= 0:
        return 0.0
    return _clamp01(raw / max_abs)


def _amount_rank_in_group(rows: list[dict[str, Any]]) -> dict[str, float]:
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
    row: dict[str, Any],
    *,
    amount_rank: float = 0.5,
    sector_strength_bonus: float = 1.0,
    resonance_bonus: float = 0.0,
    max_net_mf: float = 0.0,
    weights: dict[str, float] | None = None,
) -> float:
    w = dict(_DEFAULT_WEIGHTS)
    if weights:
        w.update(weights)

    limit_times = float(row.get("limit_times") or 0)
    if limit_times < 1 and is_at_limit_board(row):
        limit_times = 1.0

    parts = {
        "limit_times": _norm_limit_times(limit_times),
        "seal_quality": _seal_quality_proxy(row),
        "amount_rank": _clamp01(amount_rank),
        "seal_time": 0.0,
        "net_mf": _norm_net_mf(row, max_abs=max_net_mf),
        "sector_strength": _clamp01(sector_strength_bonus),
        "resonance": _clamp01(resonance_bonus),
    }
    score = sum(parts[key] * w[key] for key in w) * 100.0
    return round(max(0.0, min(100.0, score)), 1)


def rank_sector_leaders(
    candidates: list[dict[str, Any]],
    *,
    sector_key: str = "industry",
    max_per_sector: int = 5,
) -> list[LeaderScoredRow]:
    """同板块内降序；Top1=龙一，Top2=龙二，其余强势=跟风。"""
    if not candidates:
        return []

    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in candidates:
        key = str(row.get(sector_key) or "—")
        grouped.setdefault(key, []).append(dict(row))

    ranked: list[LeaderScoredRow] = []
    for group_rows in grouped.values():
        amount_ranks = _amount_rank_in_group(group_rows)
        max_mf = max(abs(float(row.get("net_mf_amount") or 0)) for row in group_rows)
        scored: list[tuple[dict[str, Any], float, float]] = []
        for row in group_rows:
            vt = str(row.get("vt_symbol") or "")
            score = compute_leader_score(
                row,
                amount_rank=amount_ranks.get(vt, 0.5),
                sector_strength_bonus=1.0,
                max_net_mf=max_mf,
            )
            boards = float(row.get("limit_times") or 0)
            if boards < 1 and is_at_limit_board(row):
                boards = 1.0
            scored.append((row, score, boards))
        scored.sort(key=lambda item: (item[1], item[2], float(item[0].get("change_pct") or 0)), reverse=True)

        for index, (row, score, boards) in enumerate(scored[:max_per_sector]):
            tier: LeaderTier
            if index == 0:
                tier = "dragon_1"
            elif index == 1:
                tier = "dragon_2"
            elif score >= _FOLLOWER_MIN_SCORE:
                tier = "follower"
            else:
                tier = ""
            if tier:
                ranked.append(LeaderScoredRow(row=row, leader_score=score, leader_tier=tier, limit_times=boards))

    ranked.sort(
        key=lambda item: (
            {"dragon_1": 3, "dragon_2": 2, "follower": 1}.get(item.leader_tier, 0),
            item.leader_score,
            float(item.row.get("change_pct") or 0),
        ),
        reverse=True,
    )
    return ranked


def score_market_leaders(
    candidates: list[dict[str, Any]],
    *,
    top_n: int = 12,
) -> list[LeaderScoredRow]:
    """全市场候选 → 板块内分层 → 按龙头分取 Top N。"""
    ranked = rank_sector_leaders(candidates)
    return ranked[: max(1, top_n)]
