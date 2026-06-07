#!/usr/bin/env python3
"""从 CSV 导入自选池或全 A 股列表到 SQLite"""

from __future__ import annotations

import argparse
from pathlib import Path

from vnpy_ashare.app_db import import_universe_csv, import_watchlist_csv
from vnpy_ashare.paths import APP_DB_PATH


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="从 CSV 导入 vnpy_zak 元数据")
    parser.add_argument("--watchlist", help="自选池 CSV，列: symbol,exchange,name")
    parser.add_argument("--universe", help="全 A 股列表 CSV，列: symbol,exchange,name")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.watchlist and not args.universe:
        raise SystemExit("请指定 --watchlist 和/或 --universe")

    if args.watchlist:
        path = Path(args.watchlist)
        if not path.exists():
            raise SystemExit(f"文件不存在: {path}")
        count = import_watchlist_csv(path)
        print(f"已导入自选池 {count} 只 <- {path}")

    if args.universe:
        path = Path(args.universe)
        if not path.exists():
            raise SystemExit(f"文件不存在: {path}")
        count = import_universe_csv(path)
        print(f"已导入全 A 股 {count} 只 <- {path}")

    print(f"写入: {APP_DB_PATH}")


if __name__ == "__main__":
    main()
