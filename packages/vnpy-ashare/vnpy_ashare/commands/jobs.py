"""后台定时任务 CLI。"""

from __future__ import annotations

import argparse

from vnpy_ashare.jobs.catalog import JOB_CATALOG
from vnpy_ashare.jobs.core.result import JobResult
from vnpy_ashare.jobs.runners import run_job


def print_job_result(result: JobResult) -> int:
    if result.skipped:
        print(result.message)
        return 0
    print(result.message)
    return 0 if result.success else 1


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
    job_run.add_argument(
        "--download-start",
        metavar="YYYY-MM-DD",
        help="batch_download_universe 起始日期，默认读调度配置",
    )
    job_run.set_defaults(handler=_cmd_job_run)
