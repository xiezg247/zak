"""可复用的后台任务（CLI / 定时调度共用）。"""

from vnpy_ashare.jobs.download import batch_download_watchlist
from vnpy_ashare.jobs.quotes import collect_market_quotes
from vnpy_ashare.jobs.result import JobResult
from vnpy_ashare.jobs.universe import sync_universe_job

__all__ = [
    "JobResult",
    "batch_download_watchlist",
    "collect_market_quotes",
    "sync_universe_job",
]
