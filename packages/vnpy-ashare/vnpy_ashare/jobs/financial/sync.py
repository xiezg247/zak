"""自选池财报同步任务。"""

from __future__ import annotations

from vnpy_ashare.integrations.tushare.client import TushareNotConfiguredError
from vnpy_ashare.jobs.core.result import JobResult
from vnpy_ashare.services.financial import sync_watchlist_financials


def sync_watchlist_financials_job(*, force: bool = False, years: int = 5) -> JobResult:
    """定时/CLI：同步自选池三表财报到 zak.db。"""
    try:
        ok, skipped, messages = sync_watchlist_financials(years=years, force=force)
    except TushareNotConfiguredError as ex:
        return JobResult(success=True, skipped=True, message=str(ex))

    if not messages:
        return JobResult(success=True, message="自选池为空")
    summary = messages[0]
    if ok == 0 and skipped == 0 and "失败" not in summary:
        return JobResult(success=False, message=summary)
    detail = "；".join(messages[1:3]) if len(messages) > 1 else ""
    text = summary if not detail else f"{summary}（{detail}）"
    return JobResult(success=True, message=text)
