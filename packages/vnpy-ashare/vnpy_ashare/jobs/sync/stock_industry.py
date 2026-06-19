"""Tushare stock_basic / 行业映射同步。"""

from __future__ import annotations

from vnpy_ashare.integrations.tushare.client import TushareNotConfiguredError, get_tushare_pro
from vnpy_ashare.integrations.tushare.factors import fetch_stock_basic_snapshot
from vnpy_ashare.integrations.tushare.sw_industry import sync_sw_industry_snapshot
from vnpy_ashare.jobs.core.result import JobResult


def sync_stock_industry_job(*, force: bool = True) -> JobResult:
    """拉取申万 2021 L2 行业映射；失败时回退 stock_basic.industry。"""
    try:
        get_tushare_pro()
    except TushareNotConfiguredError as ex:
        return JobResult(success=True, skipped=True, message=str(ex))

    mapping, count = sync_sw_industry_snapshot(force=force)
    if mapping:
        return JobResult(success=True, message=f"申万2021 L2 行业映射 {count} 条")

    rows, basic_count = fetch_stock_basic_snapshot(force=force)
    if not rows:
        return JobResult(
            success=False,
            message="未拉取到申万行业或 stock_basic（可能权限不足、网络异常或 Tushare 暂不可用）",
        )
    return JobResult(success=True, message=f"行业映射 {basic_count} 条（回退 stock_basic）")
