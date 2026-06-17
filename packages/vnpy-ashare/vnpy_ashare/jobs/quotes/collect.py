"""全市场行情采集。"""

from __future__ import annotations

from vnpy_ashare.integrations.tickflow.quotes import fetch_quotes_from_tickflow
from vnpy_ashare.jobs.core.result import JobResult
from vnpy_ashare.quotes.core.enrich import enrich_quotes_with_tushare_factors
from vnpy_ashare.quotes.core.redis_store import RedisQuoteStore
from vnpy_ashare.storage.universe import load_universe


def collect_market_quotes() -> JobResult:
    stocks = load_universe(allow_sync=False)
    quotes = fetch_quotes_from_tickflow(stocks)
    enrich_quotes_with_tushare_factors(quotes)
    store = RedisQuoteStore()
    store.ping()
    count = store.write_quotes(quotes)
    updated_at = store.get_updated_at() or "-"
    return JobResult(
        success=True,
        message=f"写入 {count} 条行情，更新于 {updated_at}",
    )
