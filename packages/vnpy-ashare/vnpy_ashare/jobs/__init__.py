"""可复用的后台任务（CLI / 定时调度共用）。

子包::

    core/      执行结果、进度日志
    sync/      标的列表、行业、交易日历、停牌
    bars/      日 K 下载与本地补全
    prefetch/  收盘后 Tushare 预拉、板块资金
    financial/ 自选池财报与披露计划
    quotes/    行情采集
    market/    市场摘要预热
    screen/    自动选股、雷达展望扫描
"""

from vnpy_ashare.jobs.bars.batch_fill import batch_fill_downloaded_stale_job
from vnpy_ashare.jobs.bars.download import batch_download_universe_daily_bars
from vnpy_ashare.jobs.core.result import JobResult
from vnpy_ashare.jobs.financial.disclosure import sync_disclosure_calendar_job
from vnpy_ashare.jobs.financial.sync import sync_watchlist_financials_job
from vnpy_ashare.jobs.market.summary_warmup import warm_market_summary
from vnpy_ashare.jobs.prefetch.concept import prefetch_concept_board
from vnpy_ashare.jobs.prefetch.moneyflow import prefetch_moneyflow
from vnpy_ashare.jobs.prefetch.sector_flow import sync_sector_flow_daily_job
from vnpy_ashare.jobs.prefetch.tushare import prefetch_tushare_factors
from vnpy_ashare.jobs.quotes.collect import collect_market_quotes
from vnpy_ashare.jobs.screen.auto_screen import run_scheduled_auto_screen
from vnpy_ashare.jobs.sync.stock_industry import sync_stock_industry_job
from vnpy_ashare.jobs.sync.suspend_sync import sync_suspend_daily_job
from vnpy_ashare.jobs.sync.trade_calendar import sync_trade_calendar_job
from vnpy_ashare.jobs.sync.universe import sync_universe_job

__all__ = [
    "JobResult",
    "batch_download_universe_daily_bars",
    "batch_fill_downloaded_stale_job",
    "collect_market_quotes",
    "prefetch_concept_board",
    "prefetch_moneyflow",
    "prefetch_tushare_factors",
    "run_scheduled_auto_screen",
    "sync_disclosure_calendar_job",
    "sync_sector_flow_daily_job",
    "sync_stock_industry_job",
    "sync_suspend_daily_job",
    "sync_trade_calendar_job",
    "sync_universe_job",
    "sync_watchlist_financials_job",
    "warm_market_summary",
]
