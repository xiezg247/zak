"""交易流水领域模型。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

JournalSide = Literal["buy", "sell", "hold"]


@dataclass(frozen=True)
class TradeJournalEntry:
    id: int
    symbol: str
    exchange: str
    side: JournalSide
    trade_date: str
    price: float
    volume: int
    mode: str
    plan_id: str | None
    on_plan: bool
    violation_tags: tuple[str, ...]
    pnl: float | None
    pnl_pct: float | None
    reason: str
    emotion_stage: str
    created_at: str

    @property
    def vt_symbol(self) -> str:
        return f"{self.symbol}.{self.exchange}"

    @property
    def amount(self) -> float:
        return round(self.price * self.volume, 2)
