"""榜单范围：自选池等个人上下文。"""

from __future__ import annotations

from collections.abc import Callable

from vnpy.trader.constant import Exchange

from vnpy_ashare.domain.symbols import StockItem, parse_tickflow_symbol
from vnpy_ashare.quotes.rank.rank_catalog import DEFAULT_RANK_ID, RankDefinition, get_rank_definition
from vnpy_ashare.quotes.rank.rank_engine import (
    finalize_rank_catalog,
    quote_matches_rank,
    quote_rank_value,
    rank_needs_post_process,
    should_finalize_rank_catalog,
)
from vnpy_ashare.quotes.core.redis_store import RedisQuoteStore
from vnpy_ashare.quotes.core.snapshot import QuoteSnapshot
from vnpy_ashare.storage.repositories.universe import load_universe_rows
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


def _sort_pool_symbols(
    tf_symbols: list[str],
    quotes: dict[str, QuoteSnapshot],
    spec: RankDefinition,
) -> list[str]:
    sort_column = spec.sort_column or spec.redis_field
    matched = [
        tf_symbol
        for tf_symbol in tf_symbols
        if (quote := quotes.get(tf_symbol)) is not None and quote.last_price > 0
    ]
    matched.sort(
        key=lambda tf_symbol: quote_rank_value(quotes[tf_symbol], sort_column),
        reverse=not spec.ascending,
    )
    return matched


def _finalize_or_sort_pool(
    pool_symbols: list[str],
    quotes: dict[str, QuoteSnapshot],
    spec: RankDefinition,
) -> list[str]:
    if should_finalize_rank_catalog(spec):
        return finalize_rank_catalog(pool_symbols, quotes, spec)
    return _sort_pool_symbols(pool_symbols, quotes, spec)


def _load_market_rank_from_universe(
    spec: RankDefinition,
    *,
    universe_quotes_loader: Callable[[list[StockItem]], dict[str, QuoteSnapshot]],
) -> tuple[list[str], dict[str, QuoteSnapshot]]:
    items = [StockItem(symbol=symbol, exchange=exchange, name=name) for symbol, exchange, name in load_universe_rows()]
    quotes = universe_quotes_loader(items)
    if rank_needs_post_process(spec):
        items = [
            item
            for item in items
            if (quote := quotes.get(item.tickflow_symbol)) is not None and quote_matches_rank(quote, spec)
        ]
    else:
        items = [
            item
            for item in items
            if (quote := quotes.get(item.tickflow_symbol)) is not None and quote.last_price > 0
        ]
    sort_column = spec.sort_column or spec.redis_field
    items.sort(
        key=lambda item: quote_rank_value(quotes[item.tickflow_symbol], sort_column)
        if quotes.get(item.tickflow_symbol) is not None
        else (float("-inf") if not spec.ascending else float("inf")),
        reverse=not spec.ascending,
    )
    return [item.tickflow_symbol for item in items], quotes


def load_market_rank_catalog(
    store: RedisQuoteStore,
    spec: RankDefinition,
    *,
    universe_quotes_loader: Callable[[list[StockItem]], dict[str, QuoteSnapshot]] | None = None,
) -> tuple[list[str], dict[str, QuoteSnapshot]]:
    """加载市场榜 tickflow 顺序：Redis 榜 ZSET → 涨幅榜池补 Tushare 因子 → 全 universe。"""
    tf_symbols = store.list_all_rank_symbols(
        field=spec.redis_field,
        ascending=spec.ascending,
    )
    if tf_symbols:
        quotes = store.get_quotes(tf_symbols)
        if should_finalize_rank_catalog(spec):
            tf_symbols = finalize_rank_catalog(tf_symbols, quotes, spec)
        if tf_symbols:
            return tf_symbols, quotes

    change_spec = get_rank_definition(DEFAULT_RANK_ID)
    pool_symbols = store.list_all_rank_symbols(
        field=change_spec.redis_field,
        ascending=change_spec.ascending,
    )
    if pool_symbols:
        quotes = store.get_quotes(pool_symbols)
        tf_symbols = _finalize_or_sort_pool(pool_symbols, quotes, spec)
        if tf_symbols:
            return tf_symbols, quotes

    if universe_quotes_loader is None:
        return [], {}
    return _load_market_rank_from_universe(spec, universe_quotes_loader=universe_quotes_loader)


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
