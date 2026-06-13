"""个股分析弹窗宿主上下文（看盘页 / 选股页等）。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from vnpy.event import EventEngine
from vnpy.trader.engine import MainEngine
from vnpy.trader.ui import QtCore

from vnpy_ashare.domain.symbols import StockItem
from vnpy_ashare.quotes import QuoteSnapshot
from vnpy_ashare.quotes.provider import resolve_quote_snapshot

if TYPE_CHECKING:
    from vnpy_ashare.ui.quotes.page.quotes_page import QuotesPage


@dataclass
class StockAnalysisHost:
    main_engine: MainEngine | None
    event_engine: EventEngine | None = None
    source_page: str = ""
    retired_workers: list[QtCore.QThread] = field(default_factory=list)
    quote_map: dict[str, QuoteSnapshot] | None = None

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
