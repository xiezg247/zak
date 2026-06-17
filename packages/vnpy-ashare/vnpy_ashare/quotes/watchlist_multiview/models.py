"""自选多维看盘行模型。"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from vnpy_ashare.domain.base import FrozenModel

WatchlistMultiSortKey = Literal["sort_order", "change_pct", "anomaly_score"]


class WatchlistMultiRow(FrozenModel):
    vt_symbol: str = Field(description="合约代码（含交易所）")
    symbol: str = Field(description="六位股票代码")
    name: str = Field(description="名称")
    sort_order: int = Field(description="排序序号")

    last_price: float | None = Field(description="最新价")
    change_pct: float | None = Field(description="涨跌幅（%）")
    volume_ratio: float | None = Field(description="量比")
    turnover_rate: float | None = Field(description="换手率（%）")
    change_speed_5m: float | None = Field(description="5 分钟涨速（%）")

    metric_label: str = Field(description="主指标标签")
    metric_value: str = Field(description="主指标值")
    sub_label: str = Field(description="副指标标签")
    sub_value: str = Field(description="副指标值")
    anomaly_score: float = Field(description="异动评分")

    signal_label: str | None = Field(default=None, description="策略信号标签")
    has_position: bool = Field(default=False, description="是否持仓")
    position_pnl_pct: float | None = Field(default=None, description="持仓盈亏比例（%）")
    industry: str | None = Field(default=None, description="所属行业")
    sector_rank: int | None = Field(default=None, description="板块内涨幅排名")
    sector_avg_change: float | None = Field(default=None, description="板块平均涨跌幅（%）")
    sparkline_points: tuple[float, ...] = Field(default=(), description="迷你图数据点")
    sparkline_kind: Literal["daily", "intraday", "minute", "none"] = Field(default="none", description="迷你图类型")


class WatchlistMultiBoardData(FrozenModel):
    rows: tuple[WatchlistMultiRow, ...] = Field(description="数据行列表")
    empty_message: str = Field(default="", description="空态提示")
    total_count: int = Field(default=0, description="总行数")
