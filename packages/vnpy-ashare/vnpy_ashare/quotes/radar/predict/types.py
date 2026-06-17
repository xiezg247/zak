"""雷达预测共享类型。"""

from __future__ import annotations

from pydantic import Field

from vnpy_ashare.domain.base import FrozenModel, MutableModel



class PredictHit(FrozenModel):
    vt_symbol: str = Field(description="合约代码（含交易所）")
    score: float = Field(description="得分")
    p_up: float = Field(description="看涨概率（0–1）")
    score_label: str = Field(description="分数标签")
    model_label: str = Field(description="模型标签")
