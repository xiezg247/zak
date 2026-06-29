"""全市场行情 Tushare 因子异步 enrich（与 collect 主路径解耦）。"""

from __future__ import annotations

from vnpy_ashare.jobs.core.result import JobResult
from vnpy_ashare.quotes.core.enrich import enrich_quotes_with_tushare_factors
from vnpy_ashare.quotes.core.quote_l1_cache import collect_defer_enrich_enabled
from vnpy_ashare.quotes.core.redis_store import RedisQuoteStore
from vnpy_common.perf_trace import tracer


def enrich_market_quotes() -> JobResult:
    """从 Redis 加载快照、合并 Tushare 因子并 PATCH 回 Redis / L1。"""
    if not collect_defer_enrich_enabled():
        return JobResult(
            success=True,
            skipped=True,
            message="ZAK_COLLECT_DEFER_ENRICH 未开启，已跳过",
        )

    with tracer.trace("enrich_market_quotes"):
        store = RedisQuoteStore()
        with tracer.trace("enrich.list_symbols"):
            tf_symbols = store.list_all_rank_symbols(field="change_pct", ascending=False)
        if not tf_symbols:
            return JobResult(success=True, message="无行情快照，跳过 enrich")

        with tracer.trace("enrich.load_quotes"):
            quotes = store.get_quotes(tf_symbols, enrich_factors=False)
        if not quotes:
            return JobResult(success=True, message="Redis 快照为空，跳过 enrich")

        with tracer.trace("enrich.tushare"):
            enrich_quotes_with_tushare_factors(quotes)

        with tracer.trace("enrich.redis_patch"):
            count = store.patch_enriched_quotes(quotes)

    tracer.summary("enrich_market_quotes")
    return JobResult(success=True, message=f"已 enrich {count} 条行情因子")
