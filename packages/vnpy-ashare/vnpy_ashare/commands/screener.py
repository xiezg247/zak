"""策略选股 CLI。"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from vnpy_ashare.ai.context.symbol import parse_stock_symbol
from vnpy_ashare.screener.batch.batch_actions import batch_download_daily_bars
from vnpy_ashare.screener.preset.scheme_store import list_schemes
from vnpy_ashare.screener.run.export import export_rows_to_csv
from vnpy_ashare.screener.run.run_store import save_run
from vnpy_ashare.screener.run.runner import (
    ScreenerRequest,
    build_scheme_config,
    list_all_preset_names,
    resolve_preset_input,
    run_screener,
)
from vnpy_ashare.storage.repositories.watchlist import add_watchlist_item


def print_screen_rows(result: Any) -> None:
    print(f"方案：{result.condition}")
    print(f"命中：{len(result.rows)} / 扫描 {result.total_scanned} · 来源 {result.source}")
    for index, row in enumerate(result.rows, start=1):
        symbol = row.get("symbol", "")
        name = row.get("name", "")
        extra = row.get("change_pct") or row.get("pe_ttm") or row.get("composite_score") or row.get("net_mf_amount") or ""
        print(f"{index:>3}. {symbol} {name} {extra}")


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

    print_screen_rows(result)

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


def register(subparsers: argparse._SubParsersAction) -> None:
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
