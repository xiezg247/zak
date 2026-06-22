"""龙头评分维度（leader_score）。"""

from __future__ import annotations

from typing import Any

from vnpy_ashare.quotes.radar.radar_leader import leader_tier_label
from vnpy_ashare.screener.data.radar_dimension_data import build_leader_score_dimension_rows
from vnpy_ashare.screener.dimensions.base import DimensionHit, quote_hits


def run_leader_score(pool_size: int, *, weight: float) -> tuple[list[DimensionHit], int]:
    rows, total = build_leader_score_dimension_rows(pool_size)
    if not rows:
        return [], total

    return quote_hits(
        rows,
        dimension_id="leader_score",
        label="龙头",
        weight=weight,
        reason_builder=_leader_score_reason,
        metric_key="leader_score",
    ), total


def _leader_score_reason(row: dict[str, Any], rank: int) -> str:
    score = float(row.get("leader_score") or 0)
    tier = leader_tier_label(str(row.get("leader_tier") or ""))
    tier_text = f"{tier} " if tier else ""
    industry = str(row.get("industry") or "—")
    return f"龙头：{tier_text}{industry} 评分 {score:.1f}，排名第 {rank}"
