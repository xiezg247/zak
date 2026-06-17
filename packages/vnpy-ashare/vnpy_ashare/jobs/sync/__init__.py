"""元数据同步：标的列表、行业、交易日历、停牌。"""

from vnpy_ashare.jobs.sync.stock_industry import sync_stock_industry_job
from vnpy_ashare.jobs.sync.suspend_sync import sync_suspend_daily_job
from vnpy_ashare.jobs.sync.trade_calendar import sync_trade_calendar_job
from vnpy_ashare.jobs.sync.universe import sync_universe_job

__all__ = [
    "sync_stock_industry_job",
    "sync_suspend_daily_job",
    "sync_trade_calendar_job",
    "sync_universe_job",
]
