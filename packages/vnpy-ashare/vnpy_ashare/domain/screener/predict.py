"""雷达预测领域模型（统计基线 / 模型命中）。"""

from __future__ import annotations

from pydantic import Field

from vnpy_common.domain.base import FrozenModel


class BaselinePredictHit(FrozenModel):
    vt_symbol: str = Field(description="合约代码（含交易所）")
    score: float = Field(description="得分")
    p_up: float = Field(description="看涨概率（0–1）")
    relative_strength: float = Field(description="相对强度（%）")
    change_pct: float = Field(description="涨跌幅（%）")
    volume_ratio: float = Field(description="量比")
    turnover_rate: float = Field(description="换手率（%）")


class PredictHit(FrozenModel):
    vt_symbol: str = Field(description="合约代码（含交易所）")
    score: float = Field(description="得分")
    p_up: float = Field(description="看涨概率（0–1）")
    score_label: str = Field(description="分数标签")
    model_label: str = Field(description="模型标签")
