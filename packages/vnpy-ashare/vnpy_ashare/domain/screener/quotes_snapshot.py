"""全市场行情快照（选股管道边界）。"""

from __future__ import annotations

from pydantic import Field

from vnpy_ashare.domain.market.quote_row import QuoteRow
from vnpy_common.domain.base import FrozenModel


class MarketQuotesSnapshot(FrozenModel):
    rows: list[QuoteRow] = Field(description="行情行列表")
    updated_at: str | None = Field(description="快照更新时间")
    total: int = Field(description="有效行情条数")
    source: str = Field(default="quote", description="数据来源标识")
