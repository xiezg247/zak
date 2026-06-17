"""情绪周期引擎（MVP：基于市场广度）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from vnpy_ashare.quotes.market.market_breadth import MarketBreadthSnapshot

EmotionStage = Literal["ice", "startup", "climax", "divergence", "recession"]

_STAGE_LABELS: dict[EmotionStage, str] = {
    "ice": "冰点",
    "startup": "启动",
    "climax": "发酵/高潮",
    "divergence": "分歧",
    "recession": "退潮",
}

_STAGE_POSITION: dict[EmotionStage, tuple[float, float]] = {
    "ice": (0.0, 0.10),
    "startup": (0.30, 0.50),
    "climax": (0.60, 0.80),
    "divergence": (0.0, 0.30),
    "recession": (0.0, 0.0),
}


@dataclass(frozen=True)
class EmotionCycleSnapshot:
    stage: EmotionStage
    stage_label: str
    position_pct_min: float
    position_pct_max: float
    position_factor: float
    allow_new_positions: bool
    limit_up_count: int
    limit_down_count: int
    up_ratio: float


def classify_emotion_cycle(breadth: MarketBreadthSnapshot) -> EmotionCycleSnapshot:
    """由市场广度近似判定五阶段（Phase 2 MVP，不含连板梯队）。"""
    up_total = breadth.up + breadth.down
    up_ratio = (breadth.up / up_total) if up_total > 0 else 0.0
    limit_up = breadth.limit_up
    limit_down = breadth.limit_down

    stage: EmotionStage
    if limit_down >= 20:
        stage = "recession"
    elif limit_down >= 15 and up_ratio < 0.35 and limit_up <= 40:
        stage = "ice"
    elif limit_up >= 80:
        stage = "climax"
    elif limit_up >= 30 and abs(limit_up - limit_down) <= 10:
        stage = "divergence"
    elif limit_up >= 50:
        stage = "startup"
    else:
        stage = "divergence"

    pct_min, pct_max = _STAGE_POSITION[stage]
    factor = (pct_min + pct_max) / 2.0 if pct_max > 0 else 0.0
    if breadth.total_amount > 0 and breadth.total_amount < 1e12:
        factor *= 0.7

    return EmotionCycleSnapshot(
        stage=stage,
        stage_label=_STAGE_LABELS[stage],
        position_pct_min=pct_min,
        position_pct_max=pct_max,
        position_factor=min(1.0, max(0.0, factor)),
        allow_new_positions=stage not in {"recession", "ice"},
        limit_up_count=limit_up,
        limit_down_count=limit_down,
        up_ratio=up_ratio,
    )


class EmotionCycleTracker:
    """阶段变更时触发回调。"""

    def __init__(self) -> None:
        self._last_stage: EmotionStage | None = None
        self._last_snapshot: EmotionCycleSnapshot | None = None

    @property
    def last_snapshot(self) -> EmotionCycleSnapshot | None:
        return self._last_snapshot

    def update(self, breadth: MarketBreadthSnapshot) -> EmotionCycleSnapshot | None:
        snapshot = classify_emotion_cycle(breadth)
        self._last_snapshot = snapshot
        if snapshot.stage == self._last_stage:
            return None
        self._last_stage = snapshot.stage
        return snapshot
