"""大盘环境指标领域模型。"""

from __future__ import annotations

from pydantic import Field

from vnpy_common.domain.base import FrozenModel


class MarketEnvironmentSnapshot(FrozenModel):
    fear_greed_index: float | None = Field(description="恐贪指数")
    fear_greed_label: str = Field(description="恐贪指数标签")
    north_money: float | None = Field(description="北向资金（百万元）")
    north_trade_date: str = Field(default="", description="北向资金交易日")
