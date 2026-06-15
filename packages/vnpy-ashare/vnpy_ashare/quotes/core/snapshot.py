"""行情快照数据结构。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class QuoteSnapshot:
    symbol: str
    name: str
    last_price: float
    prev_close: float
    open_price: float
    high_price: float
    low_price: float
    change_amount: float
    change_pct: float
    turnover_rate: float
    volume: float
    amount: float = 0.0
    amplitude: float = 0.0
    volume_ratio: float = 0.0
    net_mf_amount: float = 0.0
    change_speed_5m: float = 0.0
    limit_times: float = 0.0
    trade_time: str = ""

    @property
    def is_rise(self) -> bool:
        return self.change_amount > 0

    @property
    def is_fall(self) -> bool:
        return self.change_amount < 0

    def to_redis_hash(self) -> dict[str, str]:
        return {
            "symbol": self.symbol,
            "name": self.name,
            "last_price": str(self.last_price),
            "prev_close": str(self.prev_close),
            "open_price": str(self.open_price),
            "high_price": str(self.high_price),
            "low_price": str(self.low_price),
            "change_amount": str(self.change_amount),
            "change_pct": str(self.change_pct),
            "turnover_rate": str(self.turnover_rate),
            "volume": str(self.volume),
            "amount": str(self.amount),
            "amplitude": str(self.amplitude),
            "volume_ratio": str(self.volume_ratio),
            "net_mf_amount": str(self.net_mf_amount),
            "change_speed_5m": str(self.change_speed_5m),
            "limit_times": str(self.limit_times),
            "trade_time": self.trade_time,
        }

    @classmethod
    def from_redis_hash(cls, data: dict[str, str]) -> QuoteSnapshot | None:
        symbol = data.get("symbol", "")
        if not symbol:
            return None
        return cls(
            symbol=symbol,
            name=str(data.get("name", "")),
            last_price=float(data.get("last_price", 0) or 0),
            prev_close=float(data.get("prev_close", 0) or 0),
            open_price=float(data.get("open_price", 0) or 0),
            high_price=float(data.get("high_price", 0) or 0),
            low_price=float(data.get("low_price", 0) or 0),
            change_amount=float(data.get("change_amount", 0) or 0),
            change_pct=float(data.get("change_pct", 0) or 0),
            turnover_rate=float(data.get("turnover_rate", 0) or 0),
            volume=float(data.get("volume", 0) or 0),
            amount=float(data.get("amount", 0) or 0),
            amplitude=float(data.get("amplitude", 0) or 0),
            volume_ratio=float(data.get("volume_ratio", 0) or 0),
            net_mf_amount=float(data.get("net_mf_amount", 0) or 0),
            change_speed_5m=float(data.get("change_speed_5m", 0) or 0),
            limit_times=float(data.get("limit_times", 0) or 0),
            trade_time=str(data.get("trade_time", "")),
        )
