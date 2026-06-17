"""市场广度快照与涨跌停近似阈值。"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from vnpy_common.domain.base import FrozenModel

# 近似涨跌停阈值（未区分 ST 5% / 20% 等规则）
LIMIT_UP_PCT = 9.85
LIMIT_DOWN_PCT = -9.85

LimitSource = Literal["approx", "tushare"]


class MarketBreadthSnapshot(FrozenModel):
    up: int = Field(description="上涨家数")
    down: int = Field(description="下跌家数")
    flat: int = Field(description="平盘家数")
    limit_up: int = Field(description="涨停家数")
    limit_down: int = Field(description="跌停家数")
    total_amount: float = Field(description="样本成交额合计")
    sample_size: int = Field(description="有效样本数量")
    updated_at: str | None = Field(default=None, description="快照更新时间")
    limit_source: LimitSource = Field(default="approx", description="涨跌停计数来源")
