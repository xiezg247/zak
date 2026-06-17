"""K 线下载与本地概况。"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

from vnpy.trader.constant import Exchange, Interval
from vnpy.trader.database import get_database

from vnpy_ashare.data.bars import (
    default_minute_download_start,
    download_bars,
    download_period_bars,
    load_watchlist,
)
from vnpy_ashare.data.minute_periods import MINUTE_PERIODS
from vnpy_ashare.jobs.financial.sync import sync_watchlist_financials_job
from vnpy_ashare.services.financial import FinancialSyncResult, sync_symbol_financials


def _format_bar_date(value: datetime | None) -> str:
    if value is None:
        return "—"
    return str(value.date())


def _cmd_download_batch(args: argparse.Namespace) -> int:
    watchlist_path = Path(args.watchlist) if args.watchlist else None
    if watchlist_path is not None and not watchlist_path.exists():
        print(f"自选池文件不存在: {watchlist_path}", file=sys.stderr)
        return 1

    items = load_watchlist(watchlist_path)
    if args.symbols:
        symbol_set = set(args.symbols)
        items = [item for item in items if item.symbol in symbol_set]

    if not items:
        print("自选池为空，请通过 GUI/数据库维护自选，或使用 --watchlist 导入 CSV", file=sys.stderr)
        return 1

    interval = Interval[args.interval]
    start = datetime.strptime(args.start, "%Y-%m-%d")
    end = datetime.strptime(args.end, "%Y-%m-%d")

    print(f"数据周期: {interval.value}")
    print(f"日期范围: {start.date()} ~ {end.date()}")
    print(f"标的数量: {len(items)}")
    print("-" * 50)

    success = 0
    failed: list[str] = []

    for index, item in enumerate(items, start=1):
        label = f"{item.vt_symbol}"
        if item.name:
            label += f" ({item.name})"
        print(f"[{index}/{len(items)}] 下载 {label} ...", end=" ", flush=True)

        try:
            count = download_bars(
                symbol=item.symbol,
                exchange=item.exchange,
                interval=interval,
                start=start,
                end=end,
                output=lambda _msg: None,
            )
            print(f"OK，{count} 根")
            success += 1
        except Exception as ex:
            print(f"失败: {ex}")
            failed.append(item.vt_symbol)

        if index < len(items) and args.delay > 0:
            time.sleep(args.delay)

    print("-" * 50)
    print(f"完成: 成功 {success}，失败 {len(failed)}")
    if failed:
        print("失败列表:", ", ".join(failed))
    return 0 if not failed else 1


def _cmd_download(args: argparse.Namespace) -> int:
    exchange = Exchange[args.exchange]
    end = datetime.strptime(args.end, "%Y-%m-%d") if args.end else datetime.now()

    if args.period:
        start = datetime.strptime(args.start, "%Y-%m-%d") if args.start else default_minute_download_start(end)
        count = download_period_bars(
            symbol=args.symbol,
            exchange=exchange,
            period=args.period,
            start=start,
            end=end,
        )
        print(f"已保存 {count} 根 {args.period} K 线: {args.symbol}.{args.exchange}")
        return 0

    if not args.start:
        print("日K/小时K 下载需指定 --start", file=sys.stderr)
        return 2
    start = datetime.strptime(args.start, "%Y-%m-%d")

    count = download_bars(
        symbol=args.symbol,
        exchange=exchange,
        interval=Interval[args.interval],
        start=start,
        end=end,
    )
    print(f"已保存 {count} 根 K 线: {args.symbol}.{args.exchange}")
    return 0


def _cmd_list_bars(_args: argparse.Namespace) -> int:
    items = load_watchlist()
    db = get_database()
    overview = {(row.symbol, row.exchange): row for row in db.get_bar_overview() if row.interval == Interval.DAILY}

    print(f"{'本地代码':<16} {'名称':<10} {'根数':>6}  {'起始':<12} {'结束':<12}")
    print("-" * 62)

    missing = 0
    for item in items:
        key = (item.symbol, item.exchange)
        row = overview.get(key)
        if not row:
            print(f"{item.vt_symbol:<16} {item.name:<10} {'—':>6}  {'无数据':<12}")
            missing += 1
            continue
        print(f"{item.vt_symbol:<16} {item.name:<10} {row.count:>6}  {_format_bar_date(row.start):<12} {_format_bar_date(row.end):<12}")

    print("-" * 62)
    print(f"共 {len(items)} 只，已入库 {len(items) - missing} 只，缺失 {missing} 只")
    return 0


def _cmd_sync_financials(args: argparse.Namespace) -> int:
    years = max(1, min(int(args.years or 5), 15))
    force = bool(args.force)
    if args.watchlist:
        job_result = sync_watchlist_financials_job(force=force, years=years)
        print(job_result.message)
        return 0 if job_result.success else 1

    if not args.symbol:
        print("请指定 --symbol 或 --watchlist", file=sys.stderr)
        return 2

    sync_result: FinancialSyncResult = sync_symbol_financials(args.symbol, years=years, force=force)
    print(sync_result.message)
    if sync_result.warnings:
        print("提示:", "；".join(sync_result.warnings[:4]))
    if sync_result.skipped:
        return 0
    return 0 if sync_result.synced or sync_result.skipped else 1


def register(subparsers: argparse._SubParsersAction) -> None:
    data = subparsers.add_parser("data", help="K 线下载与本地概况")
    data_sub = data.add_subparsers(dest="data_command", required=True)

    batch = data_sub.add_parser("download-batch", help="批量下载自选池 K 线")
    batch.add_argument("--watchlist", help="从 CSV 导入自选池后再下载")
    batch.add_argument(
        "--interval",
        default="DAILY",
        choices=[item.name for item in Interval if item != Interval.TICK],
    )
    batch.add_argument("--start", required=True, help="开始日期 YYYY-MM-DD")
    batch.add_argument("--end", required=True, help="结束日期 YYYY-MM-DD")
    batch.add_argument("--delay", type=float, default=0.3, help="每只标的请求间隔（秒）")
    batch.add_argument("--symbols", nargs="*", help="仅下载指定代码")
    batch.set_defaults(handler=_cmd_download_batch)

    single = data_sub.add_parser("download", help="下载单只标的 K 线")
    single.add_argument("--symbol", required=True)
    single.add_argument("--exchange", required=True, choices=[item.name for item in Exchange])
    single.add_argument(
        "--interval",
        default="DAILY",
        choices=[item.name for item in Interval if item != Interval.TICK],
    )
    single.add_argument("--period", choices=list(MINUTE_PERIODS), help="分 K 周期（仅 1m）")
    single.add_argument("--start", help="开始日期 YYYY-MM-DD")
    single.add_argument("--end", help="结束日期 YYYY-MM-DD")
    single.set_defaults(handler=_cmd_download)

    bars = data_sub.add_parser("list-bars", help="查看自选池本地日 K 概况")
    bars.set_defaults(handler=_cmd_list_bars)

    financials = data_sub.add_parser("sync-financials", help="同步个股三表财报到本地")
    financials.add_argument("--symbol", help="vt_symbol，如 600519.SSE")
    financials.add_argument("--watchlist", action="store_true", help="同步整个自选池")
    financials.add_argument("--years", type=int, default=5, help="回溯年数，默认 5")
    financials.add_argument("--force", action="store_true", help="忽略本地 TTL 强制重拉")
    financials.set_defaults(handler=_cmd_sync_financials)
