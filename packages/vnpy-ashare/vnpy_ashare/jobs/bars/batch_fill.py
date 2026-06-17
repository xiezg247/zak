"""本地已下载日 K 批量补全（定时任务）。"""

from __future__ import annotations

from vnpy.trader.constant import Exchange

from vnpy_ashare.data.bar_health import BarMeta, bar_meta_from_overview
from vnpy_ashare.data.bar_store import iter_bar_overviews
from vnpy_ashare.data.bars import load_downloaded_stocks
from vnpy_ashare.jobs.bars.local_fill import BatchFillProgress, batch_fill_stale_daily_bars, select_stale_daily_items
from vnpy_ashare.jobs.core.progress import job_log, job_progress
from vnpy_ashare.jobs.core.result import JobResult


def build_daily_bar_meta() -> dict[tuple[str, Exchange], BarMeta]:
    """从 bar overview 构建日 K 元数据索引。"""
    meta: dict[tuple[str, Exchange], BarMeta] = {}
    for row in iter_bar_overviews(scope="daily"):
        key = (row.symbol, row.exchange)
        meta[key] = bar_meta_from_overview(row)
    return meta


def batch_fill_downloaded_stale_job() -> JobResult:
    """为本地「已下载」列表中过期的日 K 增量补全到最近交易日。"""
    stocks = load_downloaded_stocks(scope="daily")
    if not stocks:
        return JobResult(success=True, skipped=True, message="本地无已下载日 K，跳过补全")

    bar_meta = build_daily_bar_meta()
    items = select_stale_daily_items(stocks, bar_meta)
    if not items:
        job_log(f"本地 {len(stocks)} 只日 K 均已是最新")
        return JobResult(success=True, message=f"本地 {len(stocks)} 只日 K 均已是最新")

    job_log(f"待补全 {len(items)} 只过期日 K")

    def on_progress(progress: BatchFillProgress) -> None:
        job_progress(progress.current, progress.total, progress.label)

    result = batch_fill_stale_daily_bars(items, bar_meta, delay=0.3, progress=on_progress)
    success = len(result.failed) == 0
    return JobResult(success=success, message=result.message)
