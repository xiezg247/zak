"""元数据 CSV 导入导出。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from vnpy_ashare.storage.app_db import (
    export_universe_csv,
    export_watchlist_csv,
    import_universe_csv,
    import_watchlist_csv,
    load_watchlist_rows,
    universe_count,
)
from vnpy_common.paths import BACKUP_DIR, get_app_db_path


def _cmd_export(args: argparse.Namespace) -> int:
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    export_watchlist_flag = not args.universe_only
    export_universe_flag = not args.watchlist_only

    if export_watchlist_flag:
        count = export_watchlist_csv(out_dir / "watchlist.csv")
        print(f"自选池: {count} 只 -> {out_dir / 'watchlist.csv'}")

    if export_universe_flag:
        if universe_count() == 0:
            print("全 A 股列表为空，请先运行 cli.py job run sync_universe")
        else:
            count = export_universe_csv(out_dir / "universe_cn_equity_a.csv")
            print(f"全 A 股: {count} 只 -> {out_dir / 'universe_cn_equity_a.csv'}")

    if export_watchlist_flag and len(load_watchlist_rows()) == 0:
        print("提示: 自选池为空，可在 GUI 中维护或通过 data download-batch --watchlist 导入")

    print(f"数据源: {get_app_db_path()}")
    return 0


def _cmd_import(args: argparse.Namespace) -> int:
    if not args.watchlist and not args.universe:
        print("请指定 --watchlist 和/或 --universe", file=sys.stderr)
        return 2

    if args.watchlist:
        path = Path(args.watchlist)
        if not path.exists():
            print(f"文件不存在: {path}", file=sys.stderr)
            return 1
        count = import_watchlist_csv(path)
        print(f"已导入自选池 {count} 只 <- {path}")

    if args.universe:
        path = Path(args.universe)
        if not path.exists():
            print(f"文件不存在: {path}", file=sys.stderr)
            return 1
        count = import_universe_csv(path)
        print(f"已导入全 A 股 {count} 只 <- {path}")

    print(f"写入: {get_app_db_path()}")
    return 0


def register(subparsers: argparse._SubParsersAction) -> None:
    meta = subparsers.add_parser("meta", help="元数据 CSV 导入导出")
    meta_sub = meta.add_subparsers(dest="meta_command", required=True)

    export_cmd = meta_sub.add_parser("export", help="导出自选池/全 A 股到 CSV")
    export_cmd.add_argument("--out-dir", default=str(BACKUP_DIR), help="输出目录，默认 data/backup")
    export_cmd.add_argument("--universe-only", action="store_true")
    export_cmd.add_argument("--watchlist-only", action="store_true")
    export_cmd.set_defaults(handler=_cmd_export)

    import_cmd = meta_sub.add_parser("import", help="从 CSV 导入元数据")
    import_cmd.add_argument("--watchlist", help="自选池 CSV")
    import_cmd.add_argument("--universe", help="全 A 股列表 CSV")
    import_cmd.set_defaults(handler=_cmd_import)
