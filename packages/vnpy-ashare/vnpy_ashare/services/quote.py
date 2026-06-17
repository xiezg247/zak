"""行情查询与上下文状态 Service。"""

from __future__ import annotations

from typing import Any

from vnpy_ashare.ai.context import (
    AiContextData,
    build_quote_context,
    enrich_context_with_actions,
    get_ai_context,
    set_ai_context,
)
from vnpy_ashare.ai.context.market_overview import merge_market_overview_extra
from vnpy_ashare.domain.market.quote_row import QuoteRow
from vnpy_ashare.domain.symbols import StockItem
from vnpy_ashare.quotes import QuoteSnapshot
from vnpy_ashare.quotes.core.quote_rows import (
    get_market_quotes_cache as read_market_quotes_cache,
)
from vnpy_ashare.quotes.core.quote_rows import (
    set_market_quotes_cache as write_market_quotes_cache,
)
from vnpy_ashare.services.base import BaseService


class QuoteService(BaseService):
    """行情查询；终端 AI 上下文读写委托 context_store。

    - ``set_current_selection``：内部/Skill 同步，不含悬浮球快捷动作
    - ``publish_quote_context``：看盘页专用，写入后会 enrich 快捷动作
    """

    def set_current_selection(
        self,
        *,
        page: str = "",
        item: StockItem | None = None,
        quote: QuoteSnapshot | None = None,
        bar_count: int = 0,
        signal_extra: str = "",
    ) -> None:
        """写入 context_store（不含悬浮球快捷动作 enrichment）。"""
        if item is None:
            set_ai_context(AiContextData(page=page))
        else:
            set_ai_context(
                build_quote_context(
                    page=page,
                    item=item,
                    quote=quote,
                    bar_count=bar_count,
                    signal_extra=signal_extra,
                )
            )

    def publish_quote_context(
        self,
        *,
        page: str,
        item: StockItem | None = None,
        quote: QuoteSnapshot | None = None,
        bar_count: int = 0,
        signal_extra: str = "",
    ) -> None:
        """写入看盘页 AI 上下文（含悬浮球快捷动作 enrichment）。"""
        merged_extra = merge_market_overview_extra(signal_extra) if page == "市场" else signal_extra.strip()
        if item is None:
            data = AiContextData(page=page, extra=merged_extra)
        else:
            data = build_quote_context(
                page=page,
                item=item,
                quote=quote,
                bar_count=bar_count,
                signal_extra=merged_extra,
            )
        set_ai_context(enrich_context_with_actions(data))

    def get_current_context(self) -> AiContextData:
        """Skill 读取终端当前页面与选中标的。"""
        return get_ai_context()

    def set_market_quotes_cache(self, items: list[Any], quotes: dict[str, QuoteSnapshot]) -> None:
        """缓存市场页行情，供 ScreeningService / AI 选股使用。"""
        write_market_quotes_cache(items, quotes)

    def get_market_quotes_cache(self) -> list[QuoteRow]:
        return read_market_quotes_cache()
