"""从 Redis 加载全市场行情，供选股规则引擎使用。"""

from __future__ import annotations

import redis

from vnpy_ashare.domain.market.quote_row import QuoteRow, quote_row_from_stock_and_snapshot
from vnpy_ashare.domain.screener.quotes_snapshot import MarketQuotesSnapshot
from vnpy_ashare.domain.symbols.stock import parse_tickflow_symbol
from vnpy_ashare.quotes.core.redis_store import RedisQuoteStore

__all__ = ["MarketQuotesLoadError", "MarketQuotesSnapshot", "load_market_quote_rows"]


class MarketQuotesLoadError(RuntimeError):
    """行情数据不可用。"""


def load_market_quote_rows(*, enrich_factors: bool = True) -> MarketQuotesSnapshot:
    """读取 Redis 全市场快照并转为 ScreeningService 可用行。"""
    store = RedisQuoteStore()
    try:
        tf_symbols = store.list_all_rank_symbols()
        if not tf_symbols:
            raise MarketQuotesLoadError("暂无全市场行情。请在「工具 → 立即执行 → 行情采集」运行后再选股。")

        quotes = store.get_quotes(tf_symbols, enrich_factors=enrich_factors)
    except redis.RedisError as exc:
        raise MarketQuotesLoadError(f"Redis 行情读取失败：{exc}") from exc

    rows: list[QuoteRow] = []
    for tf_symbol in tf_symbols:
        quote = quotes.get(tf_symbol)
        if quote is None:
            continue
        item = parse_tickflow_symbol(tf_symbol, quote.name)
        if item is None:
            continue
        rows.append(quote_row_from_stock_and_snapshot(item, quote))

    if not rows:
        raise MarketQuotesLoadError("Redis 中无有效行情快照，请先运行行情采集。")

    return MarketQuotesSnapshot(
        rows=rows,
        updated_at=store.get_updated_at(),
        total=len(rows),
        source="quote",
    )
