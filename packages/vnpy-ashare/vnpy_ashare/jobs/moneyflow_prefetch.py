"""Tushare moneyflow 预拉（写入 app_db 日级缓存）。"""

from __future__ import annotations

from vnpy_ashare.integrations.tushare import TushareNotConfiguredError, get_tushare_pro
from vnpy_ashare.jobs.progress import job_log
from vnpy_ashare.jobs.result import JobResult
from vnpy_ashare.screener.data.data_source import fetch_moneyflow_with_fallback


def prefetch_moneyflow() -> JobResult:
    """拉取全市场个股主力资金流向到本地缓存。"""
    try:
        get_tushare_pro()
    except TushareNotConfiguredError as ex:
        return JobResult(success=True, skipped=True, message=str(ex))

    job_log("拉取全市场 moneyflow（含分档买卖额字段）…")
    mf_rows, mf_date = fetch_moneyflow_with_fallback()
    if not mf_rows:
        return JobResult(
            success=False,
            message="未拉取到 moneyflow 数据（可能非交易日、Tushare 尚未更新或权限不足）",
        )
    return JobResult(success=True, message=f"moneyflow {len(mf_rows)} 条 @ {mf_date or '-'}")
