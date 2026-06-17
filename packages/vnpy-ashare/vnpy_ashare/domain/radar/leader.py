"""雷达龙头评分领域模型。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, field_validator

from vnpy_ashare.domain.market.quote_row import QuoteRow, coerce_quote_row
from vnpy_common.domain.base import FrozenModel

LeaderTier = Literal["dragon_1", "dragon_2", "follower", ""]


class LeaderScoredRow(FrozenModel):
    row: QuoteRow = Field(description="行情行（含行业/概念等扩展列）")
    leader_score: float = Field(description="龙头评分")
    leader_tier: LeaderTier = Field(description="龙头分层")
    limit_times: float = Field(description="连板数")
    sector_axis: str = Field(default="", description="板块坐标轴")
    sector_name: str = Field(default="", description="板块名称")

    @field_validator("row", mode="before")
    @classmethod
    def _coerce_row(cls, value: Any) -> QuoteRow:
        return coerce_quote_row(value)
