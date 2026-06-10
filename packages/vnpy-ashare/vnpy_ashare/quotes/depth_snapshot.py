"""五档盘口快照。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DepthSnapshot:
    symbol: str
    bid_prices: list[float]
    bid_volumes: list[int]
    ask_prices: list[float]
    ask_volumes: list[int]
    timestamp: int = 0

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
