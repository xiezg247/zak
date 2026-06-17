"""指数历史成交额序列。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class IndexAmountPoint:
    trade_date: str
    amount_yi: float


@dataclass(frozen=True)
class IndexAmountSeries:
    ts_code: str
    label: str
    points: tuple[IndexAmountPoint, ...]
    error: str = ""

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
