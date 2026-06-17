"""K 线本地存储领域模型。"""

from __future__ import annotations

from datetime import datetime

from pydantic import Field
from vnpy.trader.constant import Exchange

from vnpy_common.domain.base import FrozenModel


class PeriodBarOverview(FrozenModel):
    symbol: str = Field(description="六位股票代码")
    exchange: Exchange = Field(description="交易所代码")
    period: str = Field(description="K 线周期")
    start: datetime = Field(description="开始日期")
    end: datetime = Field(description="结束日期")
    count: int = Field(description="数量")
