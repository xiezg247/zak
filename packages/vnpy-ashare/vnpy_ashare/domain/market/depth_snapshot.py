"""五档盘口快照领域模型。"""

from __future__ import annotations

from pydantic import Field

from vnpy_common.domain.base import MutableModel


class DepthSnapshot(MutableModel):
    symbol: str = Field(description="证券代码")
    bid_prices: list[float] = Field(description="买一至买五价格")
    bid_volumes: list[int] = Field(description="买一至买五量")
    ask_prices: list[float] = Field(description="卖一至卖五价格")
    ask_volumes: list[int] = Field(description="卖一至卖五量")
    timestamp: int = Field(default=0, description="快照时间戳（毫秒）")

    @classmethod
    def from_tickflow(cls, data: dict) -> DepthSnapshot:
        return cls(
            symbol=str(data.get("symbol", "")),
            bid_prices=[float(v) for v in data.get("bid_prices", [])],
            bid_volumes=[int(v) for v in data.get("bid_volumes", [])],
            ask_prices=[float(v) for v in data.get("ask_prices", [])],
            ask_volumes=[int(v) for v in data.get("ask_volumes", [])],
            timestamp=int(data.get("timestamp", 0) or 0),
        )

    def ask_levels(self) -> list[tuple[int, float, int]]:
        """卖五 → 卖一（展示从上到下）。"""
        levels: list[tuple[int, float, int]] = []
        count = min(len(self.ask_prices), len(self.ask_volumes), 5)
        for index in range(count - 1, -1, -1):
            level = index + 1
            levels.append((level, self.ask_prices[index], self.ask_volumes[index]))
        return levels

    def bid_levels(self) -> list[tuple[int, float, int]]:
        """买一 → 买五。"""
        levels: list[tuple[int, float, int]] = []
        count = min(len(self.bid_prices), len(self.bid_volumes), 5)
        for index in range(count):
            level = index + 1
            levels.append((level, self.bid_prices[index], self.bid_volumes[index]))
        return levels
