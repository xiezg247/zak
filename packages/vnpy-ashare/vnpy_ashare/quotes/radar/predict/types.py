"""雷达预测共享类型。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PredictHit:
    vt_symbol: str
    score: float
    p_up: float
    score_label: str
    model_label: str
