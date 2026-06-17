"""指数历史成交额序列。"""

from __future__ import annotations

from pydantic import Field

from vnpy_common.domain.base import FrozenModel


class IndexAmountPoint(FrozenModel):
    trade_date: str = Field(description="交易日 YYYY-MM-DD")
    amount_yi: float = Field(description="成交额（亿元）")


class IndexAmountSeries(FrozenModel):
    ts_code: str = Field(description="Tushare 指数代码")
    label: str = Field(description="指数展示名")
    points: tuple[IndexAmountPoint, ...] = Field(description="历史成交额序列")
    error: str = Field(default="", description="拉取错误信息")

    @property
    def latest_yi(self) -> float:
        if not self.points:
            return 0.0
        return self.points[-1].amount_yi

    @property
    def avg_yi(self) -> float:
        if not self.points:
            return 0.0
        values = [point.amount_yi for point in self.points if point.amount_yi > 0]
        if not values:
            return 0.0
        return sum(values) / len(values)

    @property
    def ratio_to_avg(self) -> float | None:
        avg = self.avg_yi
        if avg <= 0:
            return None
        return self.latest_yi / avg
