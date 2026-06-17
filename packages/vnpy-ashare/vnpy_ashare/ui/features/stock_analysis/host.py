"""个股分析弹窗宿主上下文（看盘页 / 选股页等）。"""

from __future__ import annotations

from pydantic import ConfigDict, Field

from vnpy_ashare.domain.base import MutableModel

from typing import TYPE_CHECKING

from vnpy.event import EventEngine
from vnpy.trader.engine import MainEngine
from vnpy.trader.ui import QtCore

from vnpy_ashare.domain.symbols import StockItem
from vnpy_ashare.quotes import QuoteSnapshot
from vnpy_ashare.quotes.core.provider import resolve_quote_snapshot

if TYPE_CHECKING:
    from vnpy_ashare.ui.quotes.page.quotes_page import QuotesPage


class StockAnalysisHost(MutableModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    main_engine: MainEngine | None = Field(description="VeighNa 主引擎")
    event_engine: EventEngine | None = Field(default=None, description="事件引擎")
    source_page: str = Field(default="", description="来源页面名称")
    retired_workers: list[QtCore.QThread] = Field(default_factory=list, description="待回收的后台线程")
    quote_map: dict[str, QuoteSnapshot] | None = Field(default=None, description="行情快照缓存")

    @classmethod
    def from_quotes_page(cls, page: QuotesPage) -> StockAnalysisHost:
        return cls(
            main_engine=page._get_main_engine(),
            event_engine=page.event_engine,
            source_page=page.page_name,
            retired_workers=list(getattr(page, "_retired_workers", []) or []),
            quote_map=page.quote_map,
        )

    @classmethod
    def from_main_engine(
        cls,
        main_engine: MainEngine,
        *,
        event_engine: EventEngine | None = None,
        source_page: str = "",
        retired_workers: list[QtCore.QThread] | None = None,
    ) -> StockAnalysisHost:
        return cls(
            main_engine=main_engine,
            event_engine=event_engine,
            source_page=source_page,
            retired_workers=list(retired_workers or []),
            quote_map=None,
        )

    def quote_for_item(
        self,
        item: StockItem,
        *,
        row_hint: dict[str, object] | None = None,
    ) -> QuoteSnapshot | None:
        return resolve_quote_snapshot(item, quote_map=self.quote_map, row_hint=row_hint)
