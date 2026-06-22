"""雷达共振维度（多卡加权）。"""

from __future__ import annotations

from typing import Any

from vnpy_ashare.screener.data.radar_dimension_data import build_radar_resonance_dimension_rows
from vnpy_ashare.screener.dimensions.base import DimensionHit, quote_hits


def run_radar_resonance(pool_size: int, *, weight: float) -> tuple[list[DimensionHit], int]:
    rows, total = build_radar_resonance_dimension_rows(pool_size)
    if not rows:
        return [], total

    return quote_hits(
        rows,
        dimension_id="radar_resonance",
        label="共振",
        weight=weight,
        reason_builder=_resonance_reason,
        metric_key="resonance_score",
    ), total


def _resonance_reason(row: dict[str, Any], rank: int) -> str:
    cards = int(row.get("resonance_card_count") or 0)
    score = float(row.get("resonance_score") or 0)
    name = str(row.get("name") or row.get("symbol") or "")
    return f"共振：{name} {cards}卡·{score:.1f}分，排名第 {rank}"
