"""交易计划领域模型。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

TradingPlanStatus = Literal["draft", "active", "archived"]
TradeMode = Literal["limit_board", "halfway", "pullback", "swing", "other"]


@dataclass(frozen=True)
class TradingPlanSymbolRecord:
    symbol: str
    exchange: str
    allowed_modes: tuple[str, ...]
    entry_conditions: str
    exit_conditions: str
    sort_order: int

    @property
    def vt_symbol(self) -> str:
        return f"{self.symbol}.{self.exchange}"


@dataclass(frozen=True)
class TradingPlanRecord:
    id: str
    trade_date: str
    emotion_expected: str
    max_position_pct: float
    notes: str
    status: TradingPlanStatus
    created_at: str
    updated_at: str
    symbols: tuple[TradingPlanSymbolRecord, ...]

    @property
    def watchlist_vt_symbols(self) -> tuple[str, ...]:
        return tuple(item.vt_symbol for item in self.symbols)
