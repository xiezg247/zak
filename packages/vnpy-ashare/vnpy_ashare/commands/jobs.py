"""后台定时任务 CLI。"""

from __future__ import annotations

import argparse
from collections.abc import Callable
from datetime import datetime

from vnpy_ashare.domain.market_hours import CHINA_TZ, is_ashare_trading_session, next_quotes_collect_at
from vnpy_ashare.jobs import (
    JobResult,
    batch_download_watchlist,
    batch_fill_downloaded_stale_job,
    collect_market_quotes,
    prefetch_tushare_factors,
    run_scheduled_auto_screen,
    sync_disclosure_calendar_job,
    sync_trade_calendar_job,
    sync_universe_job,
    sync_watchlist_financials_job,
)
from vnpy_ashare.scheduler.config import load_scheduler_config

_COLLECT_QUOTES_INTERVAL_MIN = 5

JOB_CATALOG: dict[str, tuple[str, str]] = {
    "collect_quotes": ("行情采集", "TickFlow 全市场快照写入 Redis"),
    "sync_universe": ("同步 A 股列表", "从 TickFlow 更新全市场标的到本地 SQLite"),
    "sync_trade_calendar": ("同步交易日历", "从 Tushare 更新 A 股交易日历到本地 SQLite"),
    "batch_download": ("下载自选日 K", "批量下载自选池日线到本地数据库"),
    "prefetch_tushare": ("Tushare 因子预拉", "收盘后拉取 daily_basic / moneyflow 等写入本地缓存"),
    "sync_watchlist_financials": ("同步自选财报", "增量拉取自选池三表与财务指标到本地"),
    "sync_disclosure_calendar": ("同步披露计划", "拉取自选池财报预约披露日期"),
    "batch_fill_stale": ("补全本地日 K", "为本地已下载列表中过期的日 K 增量补全"),
    "screen_intraday": ("盘中自动选股", "交易时段多维度选股，结果写入选股历史"),
    "screen_post_close": ("盘后自动选股", "收盘后多维度选股，结果写入选股历史"),
}

_SIMPLE_JOB_RUNNERS: dict[str, Callable[[], JobResult]] = {
    "sync_universe": sync_universe_job,
    "sync_trade_calendar": sync_trade_calendar_job,
    "prefetch_tushare": prefetch_tushare_factors,
    "sync_watchlist_financials": sync_watchlist_financials_job,
    "sync_disclosure_calendar": sync_disclosure_calendar_job,
    "batch_fill_stale": batch_fill_downloaded_stale_job,
}


def print_job_result(result: JobResult) -> int:
    if result.skipped:
        print(result.message)
        return 0
    print(result.message)
    return 0 if result.success else 1


def _run_collect_quotes(*, force: bool) -> JobResult:
    now = datetime.now(CHINA_TZ)
    cfg = load_scheduler_config().collect_quotes
    interval = max(cfg.interval_seconds, _COLLECT_QUOTES_INTERVAL_MIN)
    if not force and not is_ashare_trading_session(now):
        nxt = next_quotes_collect_at(now, interval_seconds=interval)
        return JobResult(
            success=True,
            skipped=True,
            message=f"非交易时段，已跳过（下次 {nxt.strftime('%Y-%m-%d %H:%M:%S')}）",
        )

    result = collect_market_quotes()
    if force and not is_ashare_trading_session(now):
        return JobResult(
            success=result.success,
            skipped=False,
            message=f"非交易时段手动采集 · {result.message}",
        )
    return result


def _run_batch_download(*, start: str | None) -> JobResult:
    cfg = load_scheduler_config().batch_download
    start_text = start or cfg.download_start
    start_dt = datetime.strptime(start_text, "%Y-%m-%d")
    return batch_download_watchlist(start=start_dt, end=datetime.now())


def run_job(job_id: str, *, force: bool = False, download_start: str | None = None) -> JobResult:
    """执行定时任务（与 GUI 调度器共用 jobs 实现）。"""
    if job_id not in JOB_CATALOG:
        return JobResult(success=False, message=f"未知任务：{job_id}")

    if job_id == "collect_quotes":
        return _run_collect_quotes(force=force)
    if job_id in ("screen_intraday", "screen_post_close"):
        return run_scheduled_auto_screen(job_id, force=force)
    if job_id == "batch_download":
        return _run_batch_download(start=download_start)

    runner = _SIMPLE_JOB_RUNNERS.get(job_id)
    if runner is None:
        return JobResult(success=False, message=f"未注册执行器：{job_id}")
    return runner()


def _cmd_job_list(_args: argparse.Namespace) -> int:
    print("可用后台任务：")
    for job_id, (name, description) in JOB_CATALOG.items():
        print(f"  {job_id:<20} {name} — {description}")
    return 0


def _cmd_job_run(args: argparse.Namespace) -> int:
    result = run_job(args.job_id, force=args.force, download_start=args.download_start)
    return print_job_result(result)


def register(subparsers: argparse._SubParsersAction) -> None:
    job_parser = subparsers.add_parser("job", help="后台任务（与定时调度共用）")
    job_sub = job_parser.add_subparsers(dest="job_command", required=True)

    job_list = job_sub.add_parser("list", help="列出可用任务")
    job_list.set_defaults(handler=_cmd_job_list)

    job_run = job_sub.add_parser("run", help="立即执行指定任务")
    job_run.add_argument("job_id", choices=sorted(JOB_CATALOG))
    job_run.add_argument("--force", action="store_true", help="跳过交易时段/收盘检查（行情采集、自动选股）")
    job_run.add_argument("--download-start", metavar="YYYY-MM-DD", help="batch_download 起始日期，默认读调度配置")
    job_run.set_defaults(handler=_cmd_job_run)
