"""Tushare stock_basic / 行业映射同步。"""

from __future__ import annotations

from vnpy_ashare.integrations.tushare import TushareNotConfiguredError, get_tushare_pro
from vnpy_ashare.integrations.tushare.factors import fetch_stock_basic_snapshot
from vnpy_ashare.jobs.core.result import JobResult


def sync_stock_industry_job(*, force: bool = True) -> JobResult:
    """拉取 Tushare stock_basic，更新行业映射本地缓存（供行业榜 / 筛选使用）。"""
    try:
        get_tushare_pro()
    except TushareNotConfiguredError as ex:
        return JobResult(success=True, skipped=True, message=str(ex))

    rows, count = fetch_stock_basic_snapshot(force=force)
    if not rows:
        return JobResult(
            success=False,
            message="未拉取到 stock_basic（可能权限不足、网络异常或 Tushare 暂不可用）",
        )
    return JobResult(success=True, message=f"行业映射 {count} 条（stock_basic）")
