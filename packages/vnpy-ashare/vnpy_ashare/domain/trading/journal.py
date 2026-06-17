"""交易流水领域模型。"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from vnpy_common.domain.base import FrozenModel

JournalSide = Literal["buy", "sell", "hold"]


class TradeJournalEntry(FrozenModel):
    id: int = Field(description="流水主键")
    symbol: str = Field(description="六位股票代码")
    exchange: str = Field(description="交易所代码")
    side: JournalSide = Field(description="买卖方向")
    trade_date: str = Field(description="成交日")
    price: float = Field(description="成交价")
    volume: int = Field(description="成交股数")
    mode: str = Field(description="交易模式")
    plan_id: str | None = Field(description="关联计划 ID")
    on_plan: bool = Field(description="是否按计划执行")
    violation_tags: tuple[str, ...] = Field(description="违规标签")
    pnl: float | None = Field(description="已实现盈亏")
    pnl_pct: float | None = Field(description="已实现盈亏率（%）")
    reason: str = Field(description="交易理由")
    emotion_stage: str = Field(description="情绪阶段")
    created_at: str = Field(description="创建时间")

    @property
    def vt_symbol(self) -> str:
        return f"{self.symbol}.{self.exchange}"

    @property
    def amount(self) -> float:
        return round(self.price * self.volume, 2)
