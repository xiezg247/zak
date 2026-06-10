#!/usr/bin/env python3
"""将自选池、全 A 股列表从 SQLite 导出为 CSV 备份"""

from __future__ import annotations

import argparse
from pathlib import Path

from vnpy_ashare.storage.app_db import (
    export_universe_csv,
    export_watchlist_csv,
    load_watchlist_rows,
    universe_count,
)
from vnpy_common.paths import BACKUP_DIR, get_app_db_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="导出 zak 元数据到 CSV")
    parser.add_argument(
        "--out-dir",
        default=str(BACKUP_DIR),
        help="输出目录，默认 data/backup",
    )
    parser.add_argument(
        "--universe-only",
        action="store_true",
        help="仅导出全 A 股列表",
    )
    parser.add_argument(
        "--watchlist-only",
        action="store_true",
        help="仅导出自选池",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    export_watchlist_flag = not args.universe_only
    export_universe_flag = not args.watchlist_only

    if export_watchlist_flag:
        count = export_watchlist_csv(out_dir / "watchlist.csv")
        print(f"自选池: {count} 只 -> {out_dir / 'watchlist.csv'}")

    if export_universe_flag:
        if universe_count() == 0:
            print("全 A 股列表为空，请先运行 scripts/sync_universe.py")
        else:
            count = export_universe_csv(out_dir / "universe_cn_equity_a.csv")
            print(f"全 A 股: {count} 只 -> {out_dir / 'universe_cn_equity_a.csv'}")

    if export_watchlist_flag and len(load_watchlist_rows()) == 0:
        print("提示: 自选池为空，可在 GUI 中维护或通过 batch_download --watchlist 导入")

    print(f"数据源: {get_app_db_path()}")


if __name__ == "__main__":
    main()
