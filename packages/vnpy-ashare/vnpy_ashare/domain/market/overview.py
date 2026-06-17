"""市场概览页聚合数据模型。"""

from __future__ import annotations

from pydantic import Field

from vnpy_ashare.domain.market.breadth import MarketBreadthSnapshot
from vnpy_ashare.domain.market.environment import MarketEnvironmentSnapshot
from vnpy_ashare.domain.market.quote_snapshot import QuoteSnapshot
from vnpy_common.domain.base import FrozenModel


class SectorRankItem(FrozenModel):
    industry: str = Field(description="所属行业")
    count: int = Field(description="数量")
    avg_change_pct: float = Field(description="平均涨跌幅（%）")


class MarketOverviewData(FrozenModel):
    indices: list[tuple[str, QuoteSnapshot]] = Field(description="指数列表")
    breadth: MarketBreadthSnapshot | None = Field(description="市场广度")
    sectors: list[SectorRankItem] = Field(description="行业榜")
    environment: MarketEnvironmentSnapshot | None = Field(default=None, description="大盘环境指标")
    limit_ladder_counts: dict[str, int] | None = Field(default=None, description="涨跌停梯队统计")
