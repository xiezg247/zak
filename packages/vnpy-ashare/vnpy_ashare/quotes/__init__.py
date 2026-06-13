"""行情模块：快照、Provider、TickFlow / Redis。"""

from vnpy_ashare.integrations.tickflow import MARKET_INDICES, fetch_index_ticker
from vnpy_ashare.quotes.provider import (
    QuoteProviderError,
    QuoteSource,
    fetch_quotes,
    get_quote_provider,
    get_redis_provider,
    get_tickflow_provider,
    quote_snapshot_from_row,
    resolve_quote_snapshot,
)
from vnpy_ashare.quotes.snapshot import QuoteSnapshot

__all__ = [
    "MARKET_INDICES",
    "QuoteProviderError",
    "QuoteSnapshot",
    "QuoteSource",
    "fetch_index_ticker",
    "fetch_quotes",
    "get_quote_provider",
    "get_redis_provider",
    "get_tickflow_provider",
    "quote_snapshot_from_row",
    "resolve_quote_snapshot",
]
