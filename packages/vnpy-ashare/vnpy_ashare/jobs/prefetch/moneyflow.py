"""Tushare moneyflow 预拉（写入 app_db 日级缓存）。"""

from __future__ import annotations

import os

from vnpy_ashare.data.download_concurrency import moneyflow_prefetch_max_workers, run_parallel_map
from vnpy_ashare.integrations.tushare.client import TushareNotConfiguredError, get_tushare_pro
from vnpy_ashare.integrations.tushare.factors import fetch_moneyflow
from vnpy_ashare.jobs.core.progress import job_log
from vnpy_ashare.jobs.core.result import JobResult
from vnpy_ashare.screener.data.data_source import iter_trade_date_strs


def _prefetch_lookback_days() -> int:
    raw = os.getenv("MONEYFLOW_PREFETCH_DAYS", "5").strip()
    try:
        return max(1, min(int(raw), 10))
    except ValueError:
        return 5


def prefetch_moneyflow() -> JobResult:
    """拉取近 N 个交易日全市场 moneyflow 到本地缓存。"""
    try:
        get_tushare_pro()
    except TushareNotConfiguredError as ex:
        return JobResult(success=True, skipped=True, message=str(ex))

    lookback = _prefetch_lookback_days()
    job_log(f"拉取近 {lookback} 日 moneyflow（含分档买卖额字段）…")
    trade_dates = list(iter_trade_date_strs(max_lookback=lookback))

    def _fetch_day(trade_date: str) -> str | None:
        rows, _ = fetch_moneyflow(trade_date=trade_date)
        if rows:
            return f"{trade_date}:{len(rows)}"
        return None

    workers = moneyflow_prefetch_max_workers(item_count=len(trade_dates))
    day_results = run_parallel_map(trade_dates, _fetch_day, max_workers=workers)
    fetched = [item for item in day_results if item]
    if not fetched:
        return JobResult(
            success=False,
            message="未拉取到 moneyflow 数据（可能非交易日、Tushare 尚未更新或权限不足）",
        )
    return JobResult(success=True, message="moneyflow 预拉 " + "，".join(fetched))
