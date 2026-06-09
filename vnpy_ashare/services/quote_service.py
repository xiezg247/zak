"""行情查询与上下文状态 Service。"""

from __future__ import annotations

from typing import Any

from vnpy.trader.constant import Exchange

from vnpy_ashare.ai.context import AiContextData, build_quote_context
from vnpy_ashare.ai.session_context import get_ai_context, set_ai_context
from vnpy_ashare.config import exchange_to_cn
from vnpy_ashare.models import StockItem
from vnpy_ashare.quotes import QuoteSnapshot
from vnpy_ashare.services.base import BaseService


class QuoteService(BaseService):
    """行情查询；终端上下文读写委托 session_context。"""

    def set_current_selection(
        self,
        *,
        page: str = "",
        item: StockItem | None = None,
        quote: QuoteSnapshot | None = None,
        bar_count: int = 0,
    ) -> None:
        """写入 session_context（不含悬浮球快捷动作 enrichment）。"""
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
        from vnpy_llm.ui.floating_actions import enrich_context_with_actions

        set_ai_context(enrich_context_with_actions(data))

    def get_current_context(self) -> AiContextData:
        """Skill 读取终端当前页面与选中标的。"""
        return get_ai_context()

    def get_quote(
        self, symbol: str, exchange: Exchange, quote_map: dict[str, QuoteSnapshot] | None = None
    ) -> QuoteSnapshot | None:
        """从行情映射查询快照（需外部提供 quote_map）。"""
        if quote_map is None:
            return None
        tickflow_symbol = f"{symbol}.{exchange_to_cn(exchange)}"
        return quote_map.get(tickflow_symbol)

    def get_market_rank(
        self, quotes: list[dict[str, Any]], *, top_n: int = 20
    ) -> list[dict[str, Any]]:
        """从行情列表计算涨幅榜（需外部传入行情列表）。"""
        sorted_quotes = sorted(
            quotes, key=lambda q: q.get("change_pct", 0), reverse=True
        )
        return sorted_quotes[:top_n]
