"""选股执行结果类型（打破 runner ↔ industry_screen 循环）。"""

from __future__ import annotations

from typing import Any

from pydantic import Field, field_validator

from vnpy_ashare.domain.base import MutableModel
from vnpy_ashare.domain.screener.result_row import ScreenerResultRow, coerce_screener_result_rows


class ScreenerRunResult(MutableModel):
    """单次选股执行结果。"""

    rows: list[ScreenerResultRow] = Field(description="选股结果行")
    condition: str = Field(description="选股条件描述")
    updated_at: str | None = Field(description="数据更新时间")
    total_scanned: int = Field(description="扫描标的总数")
    source: str = Field(description="数据来源标识")
    columns: list[tuple[str, str]] = Field(default_factory=list, description="导出列定义")

    @field_validator("rows", mode="before")
    @classmethod
    def _coerce_rows(cls, value: Any) -> list[ScreenerResultRow]:
        if value is None:
            return []
        return coerce_screener_result_rows(value)
