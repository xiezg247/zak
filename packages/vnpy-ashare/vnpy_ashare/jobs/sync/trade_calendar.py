"""Tushare 交易日历同步。"""

from __future__ import annotations

from datetime import date

from vnpy_ashare.integrations.tushare.client import TushareNotConfiguredError, get_tushare_pro
from vnpy_ashare.jobs.core.result import JobResult
from vnpy_ashare.storage.repositories.trade_calendar import DEFAULT_CAL_START, sync_trade_calendar


def _calendar_end(today: date | None = None) -> date:
    current = today or date.today()
    return date(current.year + 1, 12, 31)


def sync_trade_calendar_job() -> JobResult:
    """从 Tushare 同步 A 股交易日历到本地 SQLite。"""
    try:
        get_tushare_pro()
    except TushareNotConfiguredError as ex:
        return JobResult(success=True, skipped=True, message=str(ex))

    count = sync_trade_calendar(DEFAULT_CAL_START, _calendar_end())
    if count <= 0:
        return JobResult(success=False, message="交易日历同步失败（未配置 Token 或非交易日无数据）")
    return JobResult(success=True, message=f"已同步交易日历 {count} 条（{DEFAULT_CAL_START} ~ {_calendar_end()}）")
