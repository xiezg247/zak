"""榜单范围：自选池等个人上下文。"""

from __future__ import annotations

from vnpy.trader.constant import Exchange

from vnpy_ashare.domain.symbols import StockItem, parse_tickflow_symbol
from vnpy_ashare.quotes.rank.rank_catalog import RankDefinition
from vnpy_ashare.quotes.rank.rank_engine import finalize_rank_catalog
from vnpy_ashare.quotes.core.redis_store import RedisQuoteStore
from vnpy_ashare.quotes.core.snapshot import QuoteSnapshot
from vnpy_ashare.storage.repositories.watchlist import load_watchlist_rows


def load_watchlist_stock_items() -> list[StockItem]:
    return [StockItem(symbol=symbol, exchange=exchange, name=name) for symbol, exchange, name in load_watchlist_rows()]


def load_watchlist_tickflow_symbols() -> list[str]:
    return [item.tickflow_symbol for item in load_watchlist_stock_items()]


def load_watchlist_rank_catalog(
    store: RedisQuoteStore,
    spec: RankDefinition,
) -> tuple[list[str], dict[str, QuoteSnapshot]]:
    tf_symbols = load_watchlist_tickflow_symbols()
    if not tf_symbols:
        return [], {}
    quotes = store.get_quotes(tf_symbols)
    return finalize_rank_catalog(tf_symbols, quotes, spec), quotes


def build_stock_items_from_rank_symbols(
    tf_symbols: list[str],
    quotes: dict[str, QuoteSnapshot],
    *,
    name_map: dict[tuple[str, Exchange], str] | None = None,
) -> list[StockItem]:
    items: list[StockItem] = []
    for tf_symbol in tf_symbols:
        quote = quotes.get(tf_symbol)
        item = parse_tickflow_symbol(tf_symbol, quote.name if quote and quote.name else "")
        if item is None:
            continue
        if name_map:
            fallback_name = name_map.get((item.symbol, item.exchange), "")
            if fallback_name and not item.name:
                item = StockItem(symbol=item.symbol, exchange=item.exchange, name=fallback_name)
        items.append(item)
    return items


def paginate_symbols(symbols: list[str], offset: int, limit: int) -> list[str]:
    if limit <= 0:
        return []
    start = max(offset, 0)
    return list(symbols[start : start + limit])
