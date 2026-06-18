"""交易流水复盘报表领域模型。"""

from __future__ import annotations

from pydantic import Field

from vnpy_common.domain.base import FrozenModel


class JournalModeStats(FrozenModel):
    mode: str = Field(description="交易模式标识")
    sell_count: int = Field(description="卖出笔数")
    win_count: int = Field(description="盈利卖出笔数")
    loss_count: int = Field(description="亏损卖出笔数")
    win_rate_pct: float | None = Field(description="胜率（%）")
    profit_loss_ratio: float | None = Field(description="盈亏比")
    realized_pnl_total: float = Field(description="已实现盈亏合计")


class JournalReport(FrozenModel):
    total_entries: int = Field(description="流水总条数")
    buy_count: int = Field(description="买入次数")
    sell_count: int = Field(description="卖出次数")
    on_plan_count: int = Field(description="按计划交易次数")
    violation_count: int = Field(description="违规交易次数")
    off_plan_count: int = Field(description="计划外交易次数")
    add_loss_count: int = Field(description="亏损加仓次数")
    float_loss_hold_count: int = Field(description="浮亏持有次数")
    win_count: int = Field(description="盈利卖出次数")
    loss_count: int = Field(description="亏损卖出次数")
    win_rate_pct: float | None = Field(description="胜率（%）")
    profit_loss_ratio: float | None = Field(description="盈亏比")
    on_plan_ratio_pct: float | None = Field(description="按计划交易占比（%）")
    violation_ratio_pct: float | None = Field(description="违规交易占比（%）")
    realized_pnl_total: float = Field(description="已实现盈亏合计")
    avg_win: float | None = Field(description="平均盈利")
    avg_loss: float | None = Field(description="平均亏损")
    in_mode_sell_count: int = Field(default=0, description="模式内卖出笔数")
    in_mode_win_count: int = Field(default=0, description="模式内盈利卖出")
    in_mode_loss_count: int = Field(default=0, description="模式内亏损卖出")
    in_mode_win_rate_pct: float | None = Field(default=None, description="模式内胜率（%）")
    in_mode_profit_loss_ratio: float | None = Field(default=None, description="模式内盈亏比")
    in_mode_realized_pnl_total: float = Field(default=0.0, description="模式内已实现盈亏")
    mode_breakdown: tuple[JournalModeStats, ...] = Field(default_factory=tuple, description="按 mode 分组统计")

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "total_entries": self.total_entries,
            "buy_count": self.buy_count,
            "sell_count": self.sell_count,
            "on_plan_count": self.on_plan_count,
            "violation_count": self.violation_count,
            "off_plan_count": self.off_plan_count,
            "add_loss_count": self.add_loss_count,
            "float_loss_hold_count": self.float_loss_hold_count,
            "win_count": self.win_count,
            "loss_count": self.loss_count,
            "win_rate_pct": self.win_rate_pct,
            "profit_loss_ratio": self.profit_loss_ratio,
            "on_plan_ratio_pct": self.on_plan_ratio_pct,
            "violation_ratio_pct": self.violation_ratio_pct,
            "realized_pnl_total": self.realized_pnl_total,
            "avg_win": self.avg_win,
            "avg_loss": self.avg_loss,
            "in_mode_sell_count": self.in_mode_sell_count,
            "in_mode_win_count": self.in_mode_win_count,
            "in_mode_loss_count": self.in_mode_loss_count,
            "in_mode_win_rate_pct": self.in_mode_win_rate_pct,
            "in_mode_profit_loss_ratio": self.in_mode_profit_loss_ratio,
            "in_mode_realized_pnl_total": self.in_mode_realized_pnl_total,
            "mode_breakdown": [item.model_dump() for item in self.mode_breakdown],
        }
        return payload
