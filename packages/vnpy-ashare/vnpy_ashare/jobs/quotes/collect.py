"""全市场行情采集。"""

from __future__ import annotations

from vnpy_ashare.integrations.tickflow.quotes import fetch_quotes_from_tickflow
from vnpy_ashare.jobs.core.result import JobResult
from vnpy_ashare.quotes.core.enrich import enrich_quotes_with_tushare_factors
from vnpy_ashare.quotes.core.quote_l1_cache import collect_defer_enrich_enabled
from vnpy_ashare.quotes.core.redis_store import RedisQuoteStore
from vnpy_ashare.storage.universe import load_universe
from vnpy_common.perf_trace import tracer


def collect_market_quotes() -> JobResult:
    with tracer.trace("collect_market_quotes"):
        with tracer.trace("collect.universe"):
            stocks = load_universe(allow_sync=False)
        with tracer.trace("collect.tickflow"):
            quotes = fetch_quotes_from_tickflow(stocks)
        if not collect_defer_enrich_enabled():
            with tracer.trace("collect.enrich"):
                enrich_quotes_with_tushare_factors(quotes)
        store = RedisQuoteStore()
        with tracer.trace("collect.redis_ping"):
            store.ping()
        with tracer.trace("collect.redis_write"):
            count = store.write_quotes(quotes)
        updated_at = store.get_updated_at() or "-"
    tracer.summary("collect_market_quotes")
    return JobResult(
        success=True,
        message=f"写入 {count} 条行情，更新于 {updated_at}",
    )
