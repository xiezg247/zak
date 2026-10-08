"""龙头评分原语：封板质量、分项归一化、加权总分（无板块分层）。"""

from __future__ import annotations

from typing import Any, cast

from vnpy_ashare.domain.market.emotion import EmotionStage
from vnpy_ashare.domain.market.quote_row import QuoteRowLike, QuoteRowsLike, quote_row_to_dict
from vnpy_ashare.quotes.market.market_breadth import LIMIT_UP_PCT
from vnpy_ashare.screener.hard_filters import is_at_limit_board
from vnpy_ashare.trading.signals.seal_reopen import seal_reopen_from_row
from vnpy_ashare.trading.signals.seal_strength import seal_strength_from_row
from vnpy_ashare.trading.signals.seal_time import seal_time_score

__all__ = [
    "FOLLOWER_MIN_SCORE",
    "DEFAULT_WEIGHTS",
    "amount_rank_in_group",
    "batch_leader_parts_polars",
    "board_quality_score",
    "clamp01",
    "compute_leader_score",
    "compute_leader_score_breakdown",
    "leader_score_parts",
    "leader_score_weights_for_stage",
    "norm_limit_times",
    "norm_net_mf",
    "seal_quality_proxy",
]

DEFAULT_WEIGHTS: dict[str, float] = {
    "limit_times": 0.28,
    "seal_quality": 0.18,
    "amount_rank": 0.15,
    "seal_time": 0.12,
    "net_mf": 0.12,
    "sector_strength": 0.10,
    "resonance": 0.05,
}

FOLLOWER_MIN_SCORE = 35.0

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

_COMPONENT_LABELS: dict[str, str] = {
    "limit_times": "连板高度",
    "seal_quality": "封板质量",
    "amount_rank": "成交额排名",
    "seal_time": "封板时间",
    "net_mf": "主力净流入",
    "sector_strength": "板块强度",
    "resonance": "共振加成",
}


def leader_score_weights_for_stage(stage: str | None) -> dict[str, float]:
    """情绪阶段自适应权重（归一化后与默认维度键一致）。"""
    base = dict(DEFAULT_WEIGHTS)
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


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def norm_limit_times(limit_times: float) -> float:
    boards = max(0.0, limit_times)
    if boards <= 0:
        return 0.2
    return clamp01(boards / 5.0)


def seal_quality_proxy(row: QuoteRowLike) -> float:
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
        return clamp01(change / max(LIMIT_UP_PCT, 1.0) * 0.6)

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


def board_quality_score(row: QuoteRowLike) -> float | None:
    """封板质量代理 0–100（涨停 / 连板候选）。"""
    limit_times = float(row.get("limit_times") or 0)
    if limit_times < 1 and not is_at_limit_board(row):
        return None
    return round(seal_quality_proxy(row) * 100, 1)


def norm_net_mf(row: QuoteRowLike, *, max_abs: float) -> float:
    raw = float(row.get("net_mf_amount") or 0)
    if max_abs <= 0:
        return 0.5 if raw > 0 else 0.0
    if raw <= 0:
        return 0.0
    return clamp01(raw / max_abs)


def amount_rank_in_group(rows: QuoteRowsLike) -> dict[str, float]:
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
        result[vt] = clamp01(rank / n)
    return result


def leader_score_parts(
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
        "limit_times": norm_limit_times(limit_times),
        "seal_quality": seal_quality_proxy(row),
        "amount_rank": clamp01(amount_rank),
        "seal_time": clamp01(float(row.get("seal_time_score") or seal_time_score(str(row.get("first_time") or "")))),
        "net_mf": norm_net_mf(row, max_abs=max_net_mf),
        "sector_strength": clamp01(sector_strength_bonus),
        "resonance": clamp01(resonance_bonus),
    }
    return parts, limit_times


def batch_leader_parts_polars(
    rows: QuoteRowsLike,
    *,
    max_net_mf: float = 0.0,
    sector_strength_bonus: float = 1.0,
    resonance_bonus: float = 0.0,
) -> list[dict[str, float]]:
    """Polars 批量计算可向量化的龙头分项（seal_quality / seal_time 仍需 Python 逐行补齐）。"""
    import polars as pl

    row_dicts = [row.to_dict() if hasattr(row, "to_dict") else dict(row) for row in rows]
    df = pl.DataFrame(row_dicts, infer_schema_length=max(len(row_dicts), 1))
    limit_times = pl.col("limit_times").cast(pl.Float64, strict=False).fill_null(0.0)
    amount_col = pl.col("amount").cast(pl.Float64, strict=False).fill_null(0.0)
    net_mf_col = pl.col("net_mf_amount").cast(pl.Float64, strict=False).fill_null(0.0)

    amount_rank = (amount_col.rank(method="max") / pl.len()).fill_null(0.5)
    norm_limit = limit_times.clip(0.0, 5.0) / 5.0
    norm_limit = pl.when(limit_times <= 0.0).then(0.2).otherwise(norm_limit.clip(0.0, 1.0))

    if max_net_mf <= 0:
        norm_mf = pl.when(net_mf_col > 0).then(0.5).otherwise(0.0)
    else:
        norm_mf = (net_mf_col / max_net_mf).clip(0.0, 1.0)
    norm_mf = pl.when(net_mf_col <= 0).then(0.0).otherwise(norm_mf)

    df = df.with_columns(
        norm_limit.alias("_norm_limit_times"),
        amount_rank.alias("_amount_rank"),
        norm_mf.alias("_norm_net_mf"),
        pl.lit(clamp01(sector_strength_bonus)).alias("_sector_strength"),
        pl.lit(clamp01(resonance_bonus)).alias("_resonance"),
    )
    return [dict(row) for row in df.iter_rows(named=True)]


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
    w = leader_score_weights_for_stage(emotion_stage) if weights is None else dict(DEFAULT_WEIGHTS)
    if weights:
        w.update(weights)

    parts, limit_times = leader_score_parts(
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
