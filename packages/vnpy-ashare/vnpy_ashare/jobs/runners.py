"""后台任务共用执行逻辑（CLI 与调度器）。"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from vnpy_ashare.domain.time.china import china_now
from vnpy_ashare.domain.time.market_hours import is_ashare_trading_session, next_quotes_collect_at
from vnpy_ashare.jobs.bars.batch_fill import batch_fill_downloaded_stale_job
from vnpy_ashare.jobs.bars.download import batch_download_universe_daily_bars
from vnpy_ashare.jobs.bars.focus_pool_minute import batch_fill_focus_pool_minute_job
from vnpy_ashare.jobs.cache.purge_stale import purge_stale_cache_job
from vnpy_ashare.jobs.catalog import (
    COLLECT_QUOTES_INTERVAL_SECONDS,
    COLLECT_QUOTES_JOB_ID,
    ENRICH_MARKET_QUOTES_INTERVAL_SECONDS,
    ENRICH_MARKET_QUOTES_JOB_ID,
    JOB_CATALOG,
)
from vnpy_ashare.jobs.core.result import JobResult
from vnpy_ashare.jobs.feed.sync_bilibili import is_bilibili_sync_window, sync_bilibili_feed_job
from vnpy_ashare.jobs.financial.disclosure import sync_disclosure_calendar_job
from vnpy_ashare.jobs.financial.sync import sync_watchlist_financials_job
from vnpy_ashare.jobs.market.summary_warmup import warm_market_summary
from vnpy_ashare.jobs.prefetch.concept import prefetch_concept_board
from vnpy_ashare.jobs.prefetch.moneyflow import prefetch_moneyflow
from vnpy_ashare.jobs.prefetch.sector_flow import sync_sector_flow_daily_job
from vnpy_ashare.jobs.prefetch.tushare import prefetch_tushare_factors
from vnpy_ashare.jobs.quotes.collect import collect_market_quotes
from vnpy_ashare.jobs.quotes.enrich import enrich_market_quotes
from vnpy_ashare.quotes.core.quote_l1_cache import collect_defer_enrich_enabled
from vnpy_ashare.jobs.radar.card_snapshot_warmup import warm_radar_card_snapshots_job
from vnpy_ashare.jobs.screen.auto_screen import run_scheduled_auto_screen
from vnpy_ashare.jobs.screen.horizon_scan import run_horizon_outlook_scan_job
from vnpy_ashare.jobs.sync.stock_industry import sync_stock_industry_job
from vnpy_ashare.jobs.sync.suspend_sync import sync_suspend_daily_job
from vnpy_ashare.jobs.sync.trade_calendar import sync_trade_calendar_job
from vnpy_ashare.jobs.sync.universe import sync_universe_job
from vnpy_ashare.jobs.watchlist.strategy_prewarm import warm_watchlist_strategy_cache_job
from vnpy_ashare.scheduler.config import load_scheduler_config

if TYPE_CHECKING:
    from vnpy_ashare.app.engine import AshareEngine

_SIMPLE_JOB_RUNNERS: dict[str, Callable[[], JobResult]] = {
    "sync_universe": sync_universe_job,
    "sync_stock_industry": sync_stock_industry_job,
    "sync_trade_calendar": sync_trade_calendar_job,
    "batch_download_universe": batch_download_universe_daily_bars,
    "prefetch_moneyflow": prefetch_moneyflow,
    "sync_sector_flow_daily": sync_sector_flow_daily_job,
    "prefetch_concept_board": prefetch_concept_board,
    "sync_suspend_daily": sync_suspend_daily_job,
    "prefetch_tushare": prefetch_tushare_factors,
    "sync_watchlist_financials": sync_watchlist_financials_job,
    "sync_disclosure_calendar": sync_disclosure_calendar_job,
    "batch_fill_stale": batch_fill_downloaded_stale_job,
    "fill_focus_pool_minute": batch_fill_focus_pool_minute_job,
    "warm_market_summary": lambda: warm_market_summary(enrich_factors=True),
    "sync_bilibili_feed": lambda: sync_bilibili_feed_job(force=True),
    "purge_stale_cache": purge_stale_cache_job,
}


def collect_quotes_interval_seconds() -> int:
    cfg = load_scheduler_config().collect_quotes
    return max(cfg.interval_seconds, COLLECT_QUOTES_INTERVAL_SECONDS)


def enrich_market_quotes_interval_seconds() -> int:
    cfg = load_scheduler_config().enrich_market_quotes
    return max(cfg.interval_seconds, ENRICH_MARKET_QUOTES_INTERVAL_SECONDS)


def run_enrich_market_quotes(*, force: bool = False) -> JobResult:
    """行情因子 enrich（含交易时段判断）。"""
    now = china_now()
    interval = enrich_market_quotes_interval_seconds()
    if not force and not is_ashare_trading_session(now):
        nxt = next_quotes_collect_at(now, interval_seconds=interval)
        return JobResult(
            success=True,
            skipped=True,
            message=f"非交易时段，已跳过 enrich（下次 {nxt.strftime('%Y-%m-%d %H:%M:%S')}）",
        )
    result = enrich_market_quotes()
    if force and not is_ashare_trading_session(now) and not result.skipped:
        return JobResult(
            success=result.success,
            skipped=False,
            message=f"非交易时段手动 enrich · {result.message}",
        )
    return result


def run_collect_quotes(*, force: bool = False) -> JobResult:
    """行情采集（含交易时段判断与市场摘要预热）。"""
    now = china_now()
    interval = collect_quotes_interval_seconds()
    if not force and not is_ashare_trading_session(now):
        nxt = next_quotes_collect_at(now, interval_seconds=interval)
        return JobResult(
            success=True,
            skipped=True,
            message=f"非交易时段，已跳过（下次 {nxt.strftime('%Y-%m-%d %H:%M:%S')}）",
        )

    result = collect_market_quotes()
    if result.success and not result.skipped:
        if collect_defer_enrich_enabled():
            enrich = enrich_market_quotes()
            if enrich.message and not enrich.skipped:
                result = JobResult(
                    success=result.success and enrich.success,
                    skipped=result.skipped,
                    message=f"{result.message} · {enrich.message}",
                )
        warm = warm_market_summary(enrich_factors=False)
        if warm.message:
            result = JobResult(
                success=result.success,
                skipped=result.skipped,
                message=f"{result.message} · {warm.message}",
            )
    if force and not is_ashare_trading_session(now):
        return JobResult(
            success=result.success,
            skipped=False,
            message=f"非交易时段手动采集 · {result.message}",
        )
    return result


def run_prefetch_tushare_with_warm() -> JobResult:
    """Tushare 因子预拉后附带市场摘要预热。"""
    result = prefetch_tushare_factors()
    if not result.success or result.skipped:
        return result
    warm = warm_market_summary(enrich_factors=False)
    if warm.message:
        return JobResult(success=result.success, message=f"{result.message} · {warm.message}")
    return result


def run_sync_bilibili_feed(
    *,
    force: bool = False,
    engine: AshareEngine | None = None,
) -> JobResult:
    """B 站订阅同步（调度器可走 FeedService）。"""
    if not force and not is_bilibili_sync_window():
        return JobResult(
            success=True,
            skipped=True,
            message="非 08:00–20:00 时段，已跳过 B 站订阅同步",
        )
    if engine is not None:
        return engine.feed_service.sync_all_enabled()
    return sync_bilibili_feed_job(force=True)


def run_job(
    job_id: str,
    *,
    force: bool = False,
    download_start: str | None = None,
    engine: AshareEngine | None = None,
) -> JobResult:
    """执行定时任务（CLI 与 GUI 调度器共用 jobs 实现）。"""
    if job_id not in JOB_CATALOG:
        return JobResult(success=False, message=f"未知任务：{job_id}")

    if job_id == COLLECT_QUOTES_JOB_ID:
        return run_collect_quotes(force=force)
    if job_id == ENRICH_MARKET_QUOTES_JOB_ID:
        return run_enrich_market_quotes(force=force)
    if job_id in ("screen_intraday", "screen_post_close"):
        return run_scheduled_auto_screen(job_id, force=force)
    if job_id == "scan_horizon_outlook":
        return run_horizon_outlook_scan_job(force=force)
    if job_id == "warm_watchlist_strategy_cache":
        return warm_watchlist_strategy_cache_job(engine=engine, force=force)
    if job_id == "warm_radar_card_snapshots":
        return warm_radar_card_snapshots_job(force=force)
    if job_id == "batch_download_universe":
        start = download_start or load_scheduler_config().batch_download_universe.download_start
        return batch_download_universe_daily_bars(daily_start=start)
    if job_id == "sync_bilibili_feed":
        return run_sync_bilibili_feed(force=force, engine=engine)

    runner = _SIMPLE_JOB_RUNNERS.get(job_id)
    if runner is None:
        return JobResult(success=False, message=f"未注册执行器：{job_id}")
    return runner()
