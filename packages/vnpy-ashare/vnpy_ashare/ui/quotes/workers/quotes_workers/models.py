"""Worker 结果模型与共享常量。"""

from __future__ import annotations

from datetime import datetime

from pydantic import Field
from vnpy.trader.object import BarData

from vnpy_ashare.domain.market.quote_snapshot import QuoteSnapshot
from vnpy_ashare.domain.symbols.stock import StockItem
from vnpy_common.domain.base import FrozenModel, MutableModel


class MarketPageResult(MutableModel):
    """市场页分页加载结果（标的 + Redis 行情）。"""

    items: list[StockItem] = Field(description="标的列表")
    quotes: dict[str, QuoteSnapshot] = Field(description="行情快照字典（TickFlow 代码 → 快照）")
    total: int = Field(description="总条数")
    page: int = Field(description="当前页码")
    page_size: int = Field(description="每页条数")
    mode: str = Field(description="加载模式")
    updated_at: str | None = Field(default=None, description="更新时间")
    board: str | None = Field(default=None, description="板块筛选条件")


class MarketFullResult(MutableModel):
    """市场页全量加载结果（涨幅榜序 + Redis 行情）。"""

    items: list[StockItem] = Field(description="标的列表")
    quotes: dict[str, QuoteSnapshot] = Field(description="行情快照字典")
    updated_at: str | None = Field(default=None, description="更新时间")


class LoadedBars(MutableModel):
    """日 K 加载结果。"""

    item: StockItem = Field(description="当前标的")
    bars: list[BarData] = Field(description="K 线序列")
    start: datetime = Field(description="开始日期")
    end: datetime = Field(description="结束日期")


class LoadedPeriodBars(MutableModel):
    """分 K 加载结果（本地或 TickFlow 远端）。"""

    bars: list[BarData] = Field(description="K 线序列")
    from_local: bool = Field(description="是否来自本地数据库")
    period: str = Field(description="K 线周期")
    start: datetime | None = Field(default=None, description="开始日期")
    end: datetime | None = Field(default=None, description="结束日期")


class UniverseLoadResult(FrozenModel):
    items: list = Field(description="标的列表")
    total: int = Field(description="总条数")


FULL_BAR_START = datetime(2020, 1, 1)
