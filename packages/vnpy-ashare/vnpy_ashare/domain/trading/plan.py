"""交易计划领域模型。"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from vnpy_common.domain.base import FrozenModel

TradingPlanStatus = Literal["draft", "active", "archived"]
TradeMode = Literal["limit_board", "halfway", "pullback", "swing", "other"]


class TradingPlanSymbolRecord(FrozenModel):
    symbol: str = Field(description="六位股票代码")
    exchange: str = Field(description="交易所代码")
    allowed_modes: tuple[str, ...] = Field(description="允许的交易模式")
    entry_conditions: str = Field(description="入场条件说明")
    exit_conditions: str = Field(description="出场条件说明")
    sort_order: int = Field(description="排序序号")

    @property
    def vt_symbol(self) -> str:
        return f"{self.symbol}.{self.exchange}"


class TradingPlanRecord(FrozenModel):
    id: str = Field(description="计划主键")
    trade_date: str = Field(description="交易日")
    emotion_expected: str = Field(description="预期情绪阶段")
    max_position_pct: float = Field(description="最大仓位占比")
    notes: str = Field(description="备注")
    status: TradingPlanStatus = Field(description="计划状态")
    created_at: str = Field(description="创建时间")
    updated_at: str = Field(description="更新时间")
    symbols: tuple[TradingPlanSymbolRecord, ...] = Field(description="计划标的列表")

    @property
    def watchlist_vt_symbols(self) -> tuple[str, ...]:
        return tuple(item.vt_symbol for item in self.symbols)
