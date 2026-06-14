"""可复用的后台任务（CLI / 定时调度共用）。"""

from vnpy_ashare.jobs.auto_screen import run_scheduled_auto_screen
from vnpy_ashare.jobs.batch_fill_downloaded import batch_fill_downloaded_stale_job
from vnpy_ashare.jobs.concept_prefetch import prefetch_concept_board
from vnpy_ashare.jobs.disclosure_sync import sync_disclosure_calendar_job
from vnpy_ashare.jobs.financial_sync import sync_watchlist_financials_job
from vnpy_ashare.jobs.moneyflow_prefetch import prefetch_moneyflow
from vnpy_ashare.jobs.quotes import collect_market_quotes
from vnpy_ashare.jobs.result import JobResult
from vnpy_ashare.jobs.stock_industry import sync_stock_industry_job
from vnpy_ashare.jobs.suspend_sync import sync_suspend_daily_job
from vnpy_ashare.jobs.trade_calendar import sync_trade_calendar_job
from vnpy_ashare.jobs.tushare_prefetch import prefetch_tushare_factors
from vnpy_ashare.jobs.universe import sync_universe_job
from vnpy_ashare.jobs.universe_download import batch_download_universe_daily_bars

__all__ = [
    "JobResult",
    "batch_download_universe_daily_bars",
    "batch_fill_downloaded_stale_job",
    "collect_market_quotes",
    "prefetch_moneyflow",
    "prefetch_concept_board",
    "prefetch_tushare_factors",
    "run_scheduled_auto_screen",
    "sync_disclosure_calendar_job",
    "sync_stock_industry_job",
    "sync_suspend_daily_job",
    "sync_trade_calendar_job",
    "sync_universe_job",
    "sync_watchlist_financials_job",
]
