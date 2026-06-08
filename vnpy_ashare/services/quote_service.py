"""行情查询与上下文状态 Service。"""

from __future__ import annotations

import time
from typing import Any

from vnpy.trader.constant import Exchange

from vnpy_ashare.ai.context import AiContextData, build_quote_context
from vnpy_ashare.config import exchange_to_cn
from vnpy_ashare.models import StockItem
from vnpy_ashare.quotes import QuoteSnapshot
from vnpy_ashare.services.base import BaseService


class QuoteService(BaseService):
    """持有当前选中标的上下文状态 + 行情查询。"""

    def __init__(self, engine: "AshareEngine") -> None:  # type: ignore[name-defined]
        super().__init__(engine)
        self._context_cache: AiContextData | None = None
        self._context_ts: float = 0

    def set_current_selection(
        self,
        *,
        page: str = "",
        item: StockItem | None = None,
        quote: QuoteSnapshot | None = None,
        bar_count: int = 0,
    ) -> None:
        """由 QuotesPage 选择变更时调用。"""
        if item is None:
            self._context_cache = AiContextData(page=page)
        else:
            self._context_cache = build_quote_context(
                page=page,
                item=item,
                quote=quote,
                bar_count=bar_count,
            )
        self._context_ts = time.time()

    def get_current_context(self) -> AiContextData:
        """Skill 调用时 Lazy 读取。"""
        return self._context_cache or AiContextData()

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
