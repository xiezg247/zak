"""Tushare 停牌日增量同步。"""

from __future__ import annotations

from vnpy_ashare.integrations.tushare.client import TushareNotConfiguredError, get_tushare_pro
from vnpy_ashare.jobs.core.progress import job_log
from vnpy_ashare.jobs.core.result import JobResult
from vnpy_ashare.storage.repositories.symbol_suspend import DEFAULT_LOOKBACK_DAYS, sync_suspend_recent


def sync_suspend_daily_job(*, lookback_days: int = DEFAULT_LOOKBACK_DAYS) -> JobResult:
    """拉取最近若干交易日的全市场停牌记录到 PostgreSQL。"""
    try:
        get_tushare_pro()
    except TushareNotConfiguredError as ex:
        return JobResult(success=True, skipped=True, message=str(ex))

    job_log(f"同步最近 {lookback_days} 个交易日停牌记录 …")
    count, days = sync_suspend_recent(lookback_days=lookback_days)
    if not days:
        return JobResult(
            success=False,
            message="未同步停牌记录（交易日历不可用或区间无开市日）",
        )
    day_text = "、".join(day.isoformat() for day in days)
    if count <= 0:
        return JobResult(success=True, message=f"停牌记录已检查 {len(days)} 日，无新增（{day_text}）")
    return JobResult(success=True, message=f"已同步停牌记录 {count} 条 · {day_text}")
