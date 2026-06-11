"""行情 Provider：市场只读 Redis，自选 TickFlow 直连。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Literal

from vnpy_ashare.domain.models import StockItem, parse_tickflow_symbol
from vnpy_ashare.quotes.redis_store import RedisQuoteStore
from vnpy_ashare.quotes.snapshot import QuoteSnapshot
from vnpy_ashare.integrations.tickflow import MARKET_INDICES, fetch_index_ticker, fetch_quotes_from_tickflow

QuoteSource = Literal["market", "watchlist"]


class QuoteProviderError(Exception):
    """行情 Provider 不可用。"""


class QuoteProvider(ABC):
    @abstractmethod
    def get_quotes(self, items: list[StockItem]) -> dict[str, QuoteSnapshot]:
        raise NotImplementedError

    def get_rank_page(
        self,
        offset: int,
        limit: int,
    ) -> tuple[list[StockItem], dict[str, QuoteSnapshot], int]:
        raise NotImplementedError("当前 Provider 不支持涨幅榜分页")


class TickflowQuoteProvider(QuoteProvider):
    def get_quotes(self, items: list[StockItem]) -> dict[str, QuoteSnapshot]:
        return fetch_quotes_from_tickflow(items)


class RedisQuoteProvider(QuoteProvider):
    def __init__(self, store: RedisQuoteStore | None = None) -> None:
        self._store = store or RedisQuoteStore()

    def get_quotes(self, items: list[StockItem]) -> dict[str, QuoteSnapshot]:
        tf_symbols = [item.tickflow_symbol for item in items]
        return self._store.get_quotes(tf_symbols)

    def get_rank_page(
        self,
        offset: int,
        limit: int,
    ) -> tuple[list[StockItem], dict[str, QuoteSnapshot], int]:
        tf_symbols, total = self._store.get_rank_symbols(offset, limit)
        quotes = self._store.get_quotes(tf_symbols)

        items: list[StockItem] = []
        for tf_symbol in tf_symbols:
            quote = quotes.get(tf_symbol)
            item = parse_tickflow_symbol(
                tf_symbol,
                quote.name if quote and quote.name else "",
            )
            if item:
                items.append(item)
        return items, quotes, total

    def updated_at(self) -> str | None:
        return self._store.get_updated_at()


_tickflow_provider: TickflowQuoteProvider | None = None
_redis_provider: RedisQuoteProvider | None = None


def get_tickflow_provider() -> TickflowQuoteProvider:
    global _tickflow_provider
    if _tickflow_provider is None:
        _tickflow_provider = TickflowQuoteProvider()
    return _tickflow_provider


def get_redis_provider() -> RedisQuoteProvider:
    global _redis_provider
    if _redis_provider is None:
        store = RedisQuoteStore()
        try:
            store.ping()
        except Exception as ex:
            raise QuoteProviderError("Redis 不可用，市场页无法加载行情") from ex
        _redis_provider = RedisQuoteProvider(store)
    return _redis_provider


def get_quote_provider(source: QuoteSource) -> QuoteProvider:
    if source == "market":
        return get_redis_provider()
    return get_tickflow_provider()


def fetch_quotes(items: list[StockItem], source: QuoteSource) -> dict[str, QuoteSnapshot]:
    return get_quote_provider(source).get_quotes(items)


def is_gateway_quote_active() -> bool:
    """P4：Gateway 已连接且为行情主源时返回 True。"""
    return False
