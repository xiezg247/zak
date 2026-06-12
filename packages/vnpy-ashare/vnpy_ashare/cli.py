"""vnpy_ashare CLI 实现（zak 仓库入口见根目录 cli.py）。"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Callable
from datetime import datetime
from typing import Any

from dotenv import load_dotenv


def bootstrap_runtime() -> None:
    """加载 .env 并将工作目录切到仓库根（sys.path 由 vnpy_ashare.__init__ 注入）。"""
    from vnpy_common.paths import ENV_FILE, resolve_project_root

    root = resolve_project_root()
    os.environ.setdefault("ZAK_PROJECT_ROOT", str(root))
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    os.chdir(root)
    load_dotenv(ENV_FILE)


bootstrap_runtime()


from vnpy_ashare.ai.context import parse_stock_symbol
from vnpy_ashare.commands import data as data_commands
from vnpy_ashare.commands import diagnose as diagnose_commands
from vnpy_ashare.commands import meta as meta_commands
from vnpy_ashare.commands import quotes as quotes_commands
from vnpy_ashare.commands import skills as skills_commands
from vnpy_ashare.commands import tools as tools_commands
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
from vnpy_ashare.screener.batch.batch_actions import batch_download_daily_bars
from vnpy_ashare.screener.preset.scheme_store import list_schemes
from vnpy_ashare.screener.recipe.recipe import list_recipe_catalog, resolve_recipe
from vnpy_ashare.screener.recipe.recipe_runner import run_recipe
from vnpy_ashare.screener.run.export import export_rows_to_csv
from vnpy_ashare.screener.run.run_store import save_run
from vnpy_ashare.screener.run.runner import (
    ScreenerRequest,
    build_scheme_config,
    list_all_preset_names,
    resolve_preset_input,
    run_screener,
)
from vnpy_ashare.storage.app_db import add_watchlist_item, init_app_db

_COLLECT_QUOTES_INTERVAL_MIN = 5

_JOB_CATALOG: dict[str, tuple[str, str]] = {
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


def _print_job_result(result: JobResult) -> int:
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
    if job_id not in _JOB_CATALOG:
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


def _print_screen_rows(result: Any) -> None:
    print(f"方案：{result.condition}")
    print(f"命中：{len(result.rows)} / 扫描 {result.total_scanned} · 来源 {result.source}")
    for index, row in enumerate(result.rows, start=1):
        symbol = row.get("symbol", "")
        name = row.get("name", "")
        extra = row.get("change_pct") or row.get("pe_ttm") or row.get("composite_score") or row.get("net_mf_amount") or ""
        print(f"{index:>3}. {symbol} {name} {extra}")


def _cmd_job_list(_args: argparse.Namespace) -> int:
    print("可用后台任务：")
    for job_id, (name, description) in _JOB_CATALOG.items():
        print(f"  {job_id:<20} {name} — {description}")
    return 0


def _cmd_job_run(args: argparse.Namespace) -> int:
    result = run_job(args.job_id, force=args.force, download_start=args.download_start)
    return _print_job_result(result)


def _cmd_screener_list(_args: argparse.Namespace) -> int:
    print("内置与已保存方案：")
    for name in list_all_preset_names(include_saved=True):
        print(f"  - {name}")
    schemes = list_schemes()
    if schemes:
        print("\n方案 ID：")
        for scheme in schemes:
            print(f"  - {scheme.id}  {scheme.name}")
    return 0


def _cmd_screener_run(args: argparse.Namespace) -> int:
    init_app_db()

    if args.scheme_id:
        request = ScreenerRequest(preset="", top_n=args.top_n, scheme_id=args.scheme_id)
    elif args.preset:
        request = resolve_preset_input(args.preset)
        request.top_n = args.top_n
        if args.min_change is not None:
            request.min_change_pct = args.min_change
        if args.max_change is not None:
            request.max_change_pct = args.max_change
        if args.min_turnover is not None:
            request.min_turnover = args.min_turnover
    else:
        print("请指定 --preset 或 --scheme-id", file=sys.stderr)
        return 2

    try:
        result = run_screener(request)
    except Exception as ex:
        print(f"选股失败：{ex}", file=sys.stderr)
        return 1

    _print_screen_rows(result)

    if args.export:
        path = export_rows_to_csv(result.rows, args.export)
        print(f"已导出：{path}")

    if args.save_run:
        record = save_run(
            condition=result.condition,
            source=result.source,
            rows=result.rows,
            total_scanned=result.total_scanned,
            config=build_scheme_config(request),
        )
        print(f"已保存运行记录：{record.id} · {record.created_at}")

    if args.download_bars:
        dl_result = batch_download_daily_bars(result.rows)
        print(dl_result.message)
        if not dl_result.success:
            return 1

    if args.add_watchlist:
        added = 0
        for row in result.rows:
            item = parse_stock_symbol(str(row.get("vt_symbol", "")))
            if item is None:
                continue
            if add_watchlist_item(item.symbol, item.exchange, str(row.get("name", "") or item.name)):
                added += 1
        print(f"已加入自选：{added} 只")

    return 0


def _cmd_recipe_list(_args: argparse.Namespace) -> int:
    print("可用多因子配方：")
    for entry in list_recipe_catalog():
        print(f"  {entry.recipe_id:<24} {entry.display_name} ({entry.trigger_kind})")
    return 0


def _cmd_recipe_run(args: argparse.Namespace) -> int:
    init_app_db()
    recipe = resolve_recipe(args.recipe_id)
    if recipe is None:
        print(f"未知配方：{args.recipe_id}", file=sys.stderr)
        return 1

    try:
        result = run_recipe(args.recipe_id, top_n=args.top_n, condition_prefix="CLI")
    except Exception as ex:
        print(f"配方选股失败：{ex}", file=sys.stderr)
        return 1

    _print_screen_rows(result)

    if args.export:
        path = export_rows_to_csv(result.rows, args.export)
        print(f"已导出：{path}")

    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="zak", description="zak A 股终端命令行")
    subparsers = parser.add_subparsers(dest="command", required=True)

    job_parser = subparsers.add_parser("job", help="后台任务（与定时调度共用）")
    job_sub = job_parser.add_subparsers(dest="job_command", required=True)

    job_list = job_sub.add_parser("list", help="列出可用任务")
    job_list.set_defaults(handler=_cmd_job_list)

    job_run = job_sub.add_parser("run", help="立即执行指定任务")
    job_run.add_argument("job_id", choices=sorted(_JOB_CATALOG))
    job_run.add_argument("--force", action="store_true", help="跳过交易时段/收盘检查（行情采集、自动选股）")
    job_run.add_argument("--download-start", metavar="YYYY-MM-DD", help="batch_download 起始日期，默认读调度配置")
    job_run.set_defaults(handler=_cmd_job_run)

    screener_parser = subparsers.add_parser("screener", help="策略选股（预设/保存方案）")
    screener_sub = screener_parser.add_subparsers(dest="screener_command", required=True)

    screener_list = screener_sub.add_parser("list", help="列出可用方案")
    screener_list.set_defaults(handler=_cmd_screener_list)

    screener_run = screener_sub.add_parser("run", help="运行策略选股")
    screener_run.add_argument("--preset", help="内置方案名或「我的 · 方案名」")
    screener_run.add_argument("--scheme-id", help="已保存方案 ID")
    screener_run.add_argument("--top-n", type=int, default=20, help="返回条数，默认 20")
    screener_run.add_argument("--export", metavar="PATH", help="导出 CSV 路径")
    screener_run.add_argument("--add-watchlist", action="store_true", help="将结果加入自选池")
    screener_run.add_argument("--download-bars", action="store_true", help="批量下载结果日 K")
    screener_run.add_argument("--save-run", action="store_true", help="将本次选股结果写入历史")
    screener_run.add_argument("--min-change", type=float, help="自定义最低涨幅%")
    screener_run.add_argument("--max-change", type=float, help="自定义最高涨幅%")
    screener_run.add_argument("--min-turnover", type=float, help="自定义最低换手%")
    screener_run.set_defaults(handler=_cmd_screener_run)

    recipe_parser = subparsers.add_parser("recipe", help="多因子配方选股")
    recipe_sub = recipe_parser.add_subparsers(dest="recipe_command", required=True)

    recipe_list = recipe_sub.add_parser("list", help="列出可用配方")
    recipe_list.set_defaults(handler=_cmd_recipe_list)

    recipe_run = recipe_sub.add_parser("run", help="运行配方选股")
    recipe_run.add_argument("recipe_id", help="配方 ID，如 intraday_multi")
    recipe_run.add_argument("--top-n", type=int, help="返回条数，默认使用配方配置")
    recipe_run.add_argument("--export", metavar="PATH", help="导出 CSV 路径")
    recipe_run.set_defaults(handler=_cmd_recipe_run)

    data_commands.register(subparsers)
    meta_commands.register(subparsers)
    quotes_commands.register(subparsers)
    tools_commands.register(subparsers)
    skills_commands.register(subparsers)
    diagnose_commands.register(subparsers)

    return parser


def main(argv: list[str] | None = None) -> int:
    bootstrap_runtime()
    parser = _build_parser()
    args = parser.parse_args(argv)
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
