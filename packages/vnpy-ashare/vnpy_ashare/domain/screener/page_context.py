"""选股页 AI 上下文领域模型。"""

from __future__ import annotations

from typing import Any

from pydantic import Field, field_validator

from vnpy_ashare.domain.screener.result_row import ScreenerResultRow, coerce_screener_result_rows
from vnpy_common.domain.base import MutableModel


class BacktestSummary(MutableModel):
    """最近一次回测摘要。"""

    strategy: str = Field(description="策略名称")
    vt_symbol: str = Field(description="VeighNa 合约代码")
    interval: str = Field(description="K 线周期")
    start: str = Field(description="开始日期")
    end: str = Field(description="结束日期")
    statistics: dict[str, Any] = Field(default_factory=dict, description="回测统计指标")


class ScreeningResultContext(MutableModel):
    """最近一次选股结果快照（供 Skill / 悬浮球读取）。"""

    condition: str = Field(description="选股条件描述")
    count: int = Field(description="数量")
    updated_at: str | None = Field(description="更新时间")
    rows: list[ScreenerResultRow] = Field(description="数据行列表")

    @field_validator("rows", mode="before")
    @classmethod
    def _coerce_rows(cls, value: Any) -> list[ScreenerResultRow]:
        if value is None:
            return []
        return coerce_screener_result_rows(value)
