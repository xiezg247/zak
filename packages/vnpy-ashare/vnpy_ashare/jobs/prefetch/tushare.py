"""Tushare 因子预拉取（写入 app_db 日级缓存）。"""

from __future__ import annotations

from vnpy_ashare.integrations.tushare import TushareNotConfiguredError, get_tushare_pro
from vnpy_ashare.integrations.tushare.factors import (
    fetch_daily_pct_map,
    fetch_index_daily_snapshot,
    fetch_limit_list_d,
    fetch_moneyflow_hsgt_window,
    fetch_stock_basic_snapshot,
)
from vnpy_ashare.jobs.progress import job_log
from vnpy_ashare.jobs.result import JobResult
from vnpy_ashare.screener.data.data_source import fetch_daily_basic_with_fallback


def prefetch_tushare_factors() -> JobResult:
    """拉取选股与情绪分析常用 Tushare 数据到本地缓存。

    含 daily_basic / daily 涨跌幅 / stock_basic /
    limit_list_d / index_daily / moneyflow_hsgt。
    个股主力资金见独立任务 prefetch_moneyflow。
    """
    try:
        get_tushare_pro()
    except TushareNotConfiguredError as ex:
        return JobResult(success=True, skipped=True, message=str(ex))

    parts: list[str] = []
    job_log("拉取 daily_basic …")
    basic_rows, basic_date = fetch_daily_basic_with_fallback()
    parts.append(f"daily_basic {len(basic_rows)} 条 @ {basic_date or '-'}")
    job_log(parts[-1])

    anchor_date = basic_date
    if anchor_date:
        job_log("拉取 daily_pct …")
        pct_map = fetch_daily_pct_map(anchor_date)
        parts.append(f"daily_pct {len(pct_map)} 条 @ {anchor_date}")
        job_log(parts[-1])

        job_log("拉取 limit_list_d …")
        limit_rows, limit_date = fetch_limit_list_d(trade_date=anchor_date)
        parts.append(f"limit_list_d {len(limit_rows)} 条 @ {limit_date or '-'}")
        job_log(parts[-1])

        job_log("拉取 index_daily …")
        index_rows, index_date = fetch_index_daily_snapshot(trade_date=anchor_date)
        parts.append(f"index_daily {len(index_rows)} 条 @ {index_date or '-'}")
        job_log(parts[-1])

        job_log("拉取 moneyflow_hsgt …")
        hsgt_rows, hsgt_date = fetch_moneyflow_hsgt_window(trade_date=anchor_date)
        parts.append(f"moneyflow_hsgt {len(hsgt_rows)} 条 @ {hsgt_date or '-'}")
        job_log(parts[-1])

    job_log("拉取 stock_basic …")
    basic_snapshot, basic_count = fetch_stock_basic_snapshot()
    parts.append(f"stock_basic {basic_count} 条")
    job_log(parts[-1])

    if not basic_rows:
        return JobResult(
            success=False,
            message="未拉取到因子数据（可能非交易日、Tushare 尚未更新或权限不足）",
        )
    if not basic_snapshot and anchor_date:
        parts.append("stock_basic 未更新")
    return JobResult(success=True, message="；".join(parts))
