"""从 Redis 加载全市场行情，供选股规则引擎使用。"""

from __future__ import annotations

import redis

from vnpy_ashare.domain.market.quote_row import QuoteRow, quote_row_from_stock_and_snapshot
from vnpy_ashare.domain.market.quote_snapshot import QuoteSnapshot
from vnpy_ashare.domain.screener.quotes_snapshot import MarketQuotesSnapshot
from vnpy_ashare.domain.symbols.stock import parse_tickflow_symbol
from vnpy_ashare.quotes.core.enrich import backfill_rank_scores_from_zset, fill_missing_tushare_factors
from vnpy_ashare.quotes.core.quote_l1_cache import (
    get_updated_at as l1_get_updated_at,
    quote_l1_enabled,
    seq_matches,
    try_get_all_quotes,
    try_list_rank_symbols,
)
from vnpy_ashare.quotes.core.redis_store import RedisQuoteStore, get_redis_quote_store
from vnpy_common.perf_trace import tracer

__all__ = ["MarketQuotesLoadError", "MarketQuotesSnapshot", "load_market_quote_rows"]


class MarketQuotesLoadError(RuntimeError):
    """行情数据不可用。"""


def _rows_from_quote_map(quotes: dict[str, QuoteSnapshot]) -> list[QuoteRow]:
    rows: list[QuoteRow] = []
    for tf_symbol, quote in quotes.items():
        item = parse_tickflow_symbol(tf_symbol, quote.name)
        if item is None:
            continue
        rows.append(quote_row_from_stock_and_snapshot(item, quote))
    return rows


def _load_from_l1(*, enrich_factors: bool) -> MarketQuotesSnapshot | None:
    if not quote_l1_enabled():
        return None
    if not seq_matches(get_redis_quote_store().get_quote_seq()):
        return None
    with tracer.trace("quotes.l1_hit"):
        tf_symbols = try_list_rank_symbols()
        quotes = try_get_all_quotes()
        if not tf_symbols or quotes is None:
            return None
        if enrich_factors:
            fill_missing_tushare_factors(quotes)
            backfill_rank_scores_from_zset(get_redis_quote_store(), quotes)
        rows = _rows_from_quote_map(quotes)
        if not rows:
            return None
        return MarketQuotesSnapshot(
            rows=rows,
            updated_at=l1_get_updated_at(),
            total=len(rows),
            source="l1",
        )


def load_market_quote_rows(*, enrich_factors: bool = True) -> MarketQuotesSnapshot:
    """读取 Redis 全市场快照并转为 ScreeningService 可用行。"""
    with tracer.trace("load_market_quote_rows"):
        l1_snapshot = _load_from_l1(enrich_factors=enrich_factors)
        if l1_snapshot is not None:
            return l1_snapshot

        store = RedisQuoteStore()
        try:
            with tracer.trace("quotes.list_rank_symbols"):
                tf_symbols = store.list_all_rank_symbols()
            if not tf_symbols:
                raise MarketQuotesLoadError("暂无全市场行情。请在「工具 → 立即执行 → 行情采集」运行后再选股。")

            with tracer.trace("quotes.redis_get_quotes"):
                quotes = store.get_quotes(tf_symbols, enrich_factors=enrich_factors)
        except redis.RedisError as exc:
            raise MarketQuotesLoadError(f"Redis 行情读取失败：{exc}") from exc

        with tracer.trace("quotes.build_rows"):
            rows = _rows_from_quote_map({tf: quotes[tf] for tf in tf_symbols if tf in quotes})

        if not rows:
            raise MarketQuotesLoadError("Redis 中无有效行情快照，请先运行行情采集。")

        return MarketQuotesSnapshot(
            rows=rows,
            updated_at=store.get_updated_at(),
            total=len(rows),
            source="quote",
        )
