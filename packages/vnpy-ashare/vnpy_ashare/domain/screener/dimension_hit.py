"""选股维度命中领域模型。"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import Field, field_validator

from vnpy_ashare.domain.market.quote_row import QuoteRow, QuoteRowLike
from vnpy_ashare.domain.screener.result_row import ScreenerResultRow
from vnpy_common.domain.base import MutableModel


class DimensionHit(MutableModel):
    """单维度命中记录。"""

    vt_symbol: str = Field(description="标的 vt_symbol")
    dimension_id: str = Field(description="维度标识")
    label: str = Field(description="维度展示名")
    weight: float = Field(description="维度权重")
    score: float = Field(description="维度得分")
    reason: str = Field(description="命中原因")
    row: ScreenerResultRow = Field(description="结构化行情行（含维度扩展列）")

    @field_validator("row", mode="before")
    @classmethod
    def _coerce_hit_row(cls, value: Any) -> ScreenerResultRow:
        return dimension_hit_row(value)


def dimension_hit_row(row: QuoteRowLike | ScreenerResultRow | Mapping[str, Any]) -> ScreenerResultRow:
    """维度命中行归一化为 ``ScreenerResultRow``。"""
    if isinstance(row, ScreenerResultRow):
        return row
    if isinstance(row, QuoteRow):
        return ScreenerResultRow.from_quote_row(row)
    return ScreenerResultRow.from_mapping(row)
