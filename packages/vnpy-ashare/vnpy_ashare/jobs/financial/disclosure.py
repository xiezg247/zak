"""披露计划同步任务。"""

from __future__ import annotations

from vnpy_ashare.integrations.tushare.client import TushareNotConfiguredError
from vnpy_ashare.jobs.core.result import JobResult
from vnpy_ashare.services.stock.profile import sync_watchlist_disclosure


def sync_disclosure_calendar_job() -> JobResult:
    """定时/CLI：同步自选池财报披露计划。"""
    try:
        total, messages = sync_watchlist_disclosure()
    except TushareNotConfiguredError as ex:
        return JobResult(success=True, skipped=True, message=str(ex))

    if not messages:
        return JobResult(success=True, message="自选池为空")
    summary = messages[0]
    detail = "；".join(messages[1:3]) if len(messages) > 1 else ""
    text = summary if not detail else f"{summary}（{detail}）"
    return JobResult(success=True, message=text)
