"""行情模块：快照、Provider、TickFlow / Redis。"""

from __future__ import annotations

from vnpy_ashare.domain.market.indices import MARKET_INDICES
from vnpy_ashare.integrations.tickflow.quotes import fetch_index_ticker
from vnpy_ashare.quotes.core.provider import (
    QuoteProviderError,
    QuoteSource,
    fetch_quotes,
    get_quote_provider,
    get_redis_provider,
    get_tickflow_provider,
    quote_snapshot_from_row,
    resolve_quote_snapshot,
)
from vnpy_ashare.domain.market.quote_snapshot import QuoteSnapshot

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
