"""Tushare 因子预拉取（写入 app_db 日级缓存）。"""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor

from vnpy_ashare.data.download_concurrency import (
    run_parallel_map,
    tushare_anchor_prefetch_max_workers,
    tushare_prefetch_stage_max_workers,
)
from vnpy_ashare.domain.time.calendar import last_trading_day
from vnpy_ashare.integrations.tushare.client import TushareNotConfiguredError, get_tushare_pro
from vnpy_ashare.integrations.tushare.factors import (
    fetch_daily_pct_map,
    fetch_daily_turnover_total_yuan,
    fetch_index_daily_snapshot,
    fetch_limit_list_d,
    fetch_moneyflow_hsgt_window,
    fetch_stock_basic_snapshot,
)
from vnpy_ashare.integrations.tushare.stk_shock import (
    fetch_stk_high_shock_daily,
    fetch_stk_shock_daily,
)
from vnpy_ashare.jobs.core.progress import job_log
from vnpy_ashare.jobs.core.result import JobResult
from vnpy_ashare.jobs.sync.stock_industry import sync_stock_industry_job
from vnpy_ashare.screener.data.data_source import fetch_daily_basic_with_fallback


def _prefetch_anchor_datasets(anchor_date: str) -> list[str]:
    """anchor_date 确定后，并行拉取互不依赖的 Tushare 数据集。"""
    shock_date = anchor_date
    hsgt_end = last_trading_day().strftime("%Y%m%d")

    def _task_daily_pct() -> str:
        pct_map = fetch_daily_pct_map(anchor_date)
        return f"daily_pct {len(pct_map)} 条 @ {anchor_date}"

    def _task_limit_list() -> str:
        limit_rows, limit_date = fetch_limit_list_d(trade_date=anchor_date)
        return f"limit_list_d {len(limit_rows)} 条 @ {limit_date or '-'}"

    def _task_index_daily() -> str:
        index_rows, index_date = fetch_index_daily_snapshot(trade_date=anchor_date)
        return f"index_daily {len(index_rows)} 条 @ {index_date or '-'}"

    def _task_moneyflow_hsgt() -> str:
        hsgt_rows, hsgt_date = fetch_moneyflow_hsgt_window(trade_date=hsgt_end, force=True)
        return f"moneyflow_hsgt {len(hsgt_rows)} 条 @ {hsgt_date or '-'}"

    def _task_turnover() -> str:
        turnover_yuan = fetch_daily_turnover_total_yuan(anchor_date, force=True)
        turnover_trillion = turnover_yuan / 1e12 if turnover_yuan > 0 else 0.0
        return f"daily_amount {turnover_trillion:.2f} 万亿 @ {anchor_date}"

    def _task_stk_shock() -> str:
        shock_rows = fetch_stk_shock_daily(shock_date)
        high_shock_rows = fetch_stk_high_shock_daily(shock_date)
        return f"stk_shock {len(shock_rows)} + high {len(high_shock_rows)} @ {shock_date}"

    tasks: list[Callable[[], str]] = [
        _task_daily_pct,
        _task_limit_list,
        _task_index_daily,
        _task_moneyflow_hsgt,
        _task_turnover,
        _task_stk_shock,
    ]
    workers = tushare_anchor_prefetch_max_workers(item_count=len(tasks))
    messages = run_parallel_map(tasks, lambda task: task(), max_workers=workers)
    for message in messages:
        job_log(message)
    return messages


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
    basic_snapshot: list = []
    basic_count = 0
    if anchor_date:
        job_log("并行拉取 daily_pct / limit_list_d / index_daily / stock_basic / …")

        def _fetch_stock_basic() -> tuple[list, int]:
            return fetch_stock_basic_snapshot()

        with ThreadPoolExecutor(max_workers=tushare_prefetch_stage_max_workers(item_count=2)) as pool:
            anchor_future = pool.submit(_prefetch_anchor_datasets, anchor_date)
            stock_future = pool.submit(_fetch_stock_basic)
            parts.extend(anchor_future.result())
            basic_snapshot, basic_count = stock_future.result()
        stock_msg = f"stock_basic {basic_count} 条"
        parts.append(stock_msg)
        job_log(stock_msg)
    else:
        job_log("拉取 stock_basic …")
        basic_snapshot, basic_count = fetch_stock_basic_snapshot()
        parts.append(f"stock_basic {basic_count} 条")
        job_log(parts[-1])

    job_log("同步行业映射 …")
    industry_result = sync_stock_industry_job(force=False)
    if industry_result.message:
        parts.append(industry_result.message)
        job_log(industry_result.message)

    if not basic_rows:
        return JobResult(
            success=False,
            message="未拉取到因子数据（可能非交易日、Tushare 尚未更新或权限不足）",
        )
    if not basic_snapshot and anchor_date:
        parts.append("stock_basic 未更新")
    return JobResult(success=True, message="；".join(parts))
