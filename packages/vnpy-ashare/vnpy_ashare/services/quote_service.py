"""行情查询与上下文状态 Service。"""

from __future__ import annotations

from typing import Any

from vnpy.trader.constant import Exchange

from vnpy_ashare.ai.context import AiContextData, build_quote_context
from vnpy_ashare.ai.context_store import (
    get_ai_context,
    get_market_quotes_cache,
    set_ai_context,
    set_market_quotes_cache,
)
from vnpy_ashare.ai.floating_actions import enrich_context_with_actions
from vnpy_ashare.config import exchange_to_cn
from vnpy_ashare.domain.models import StockItem
from vnpy_ashare.quotes import QuoteSnapshot
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
                )
            )

    def publish_quote_context(
        self,
        *,
        page: str,
        item: StockItem | None = None,
        quote: QuoteSnapshot | None = None,
        bar_count: int = 0,
    ) -> None:
        """写入看盘页 AI 上下文（含悬浮球快捷动作 enrichment）。"""
        if item is None:
            data = AiContextData(page=page)
        else:
            data = build_quote_context(
                page=page,
                item=item,
                quote=quote,
                bar_count=bar_count,
            )
        set_ai_context(enrich_context_with_actions(data))

    def get_current_context(self) -> AiContextData:
        """Skill 读取终端当前页面与选中标的。"""
        return get_ai_context()

    def set_market_quotes_cache(self, items: list[Any], quotes: dict[str, QuoteSnapshot]) -> None:
        """缓存市场页行情，供 ScreeningService / AI 选股使用。"""
        set_market_quotes_cache(items, quotes)

    def get_market_quotes_cache(self) -> list[dict[str, Any]]:
        return get_market_quotes_cache()

    def get_quote(self, symbol: str, exchange: Exchange, quote_map: dict[str, QuoteSnapshot] | None = None) -> QuoteSnapshot | None:
        """从行情映射查询快照（需外部提供 quote_map）。"""
        if quote_map is None:
            return None
        tickflow_symbol = f"{symbol}.{exchange_to_cn(exchange)}"
        return quote_map.get(tickflow_symbol)

    def get_market_rank(self, quotes: list[dict[str, Any]], *, top_n: int = 20) -> list[dict[str, Any]]:
        """从行情列表计算涨幅榜（需外部传入行情列表）。"""
        sorted_quotes = sorted(quotes, key=lambda q: q.get("change_pct", 0), reverse=True)
        return sorted_quotes[:top_n]
