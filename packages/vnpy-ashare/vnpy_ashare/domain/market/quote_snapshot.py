"""TickFlow / Redis 行情快照领域模型。"""

from __future__ import annotations

from pydantic import Field

from vnpy_common.domain.base import MutableModel


class QuoteSnapshot(MutableModel):
    symbol: str = Field(description="证券代码")
    name: str = Field(description="证券名称")
    last_price: float = Field(description="最新价")
    prev_close: float = Field(description="昨收价")
    open_price: float = Field(description="开盘价")
    high_price: float = Field(description="最高价")
    low_price: float = Field(description="最低价")
    change_amount: float = Field(description="涨跌额")
    change_pct: float = Field(description="涨跌幅（%）")
    turnover_rate: float = Field(description="换手率（%）")
    volume: float = Field(description="成交量")
    amount: float = Field(default=0.0, description="成交额")
    amplitude: float = Field(default=0.0, description="振幅（%）")
    volume_ratio: float = Field(default=0.0, description="量比")
    net_mf_amount: float = Field(default=0.0, description="主力净流入（万元）")
    change_speed_5m: float = Field(default=0.0, description="5 分钟涨速（%）")
    limit_times: float = Field(default=0.0, description="连板数")
    trade_time: str = Field(default="", description="行情时间戳")

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
