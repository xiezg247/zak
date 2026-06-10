#!/usr/bin/env python3
"""从自选池批量下载 K 线到本地数据库（SQLite / PostgreSQL）"""

from __future__ import annotations

import argparse
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from vnpy.trader.constant import Interval

from vnpy_ashare.bars import download_bars, load_watchlist
from vnpy_common.paths import ENV_FILE


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="批量下载自选池 K 线")
    parser.add_argument(
        "--watchlist",
        default=None,
        help="从 CSV 导入自选池后再下载（列: symbol,exchange,name）；默认读 SQLite",
    )
    parser.add_argument(
        "--interval",
        default="DAILY",
        choices=[item.name for item in Interval if item != Interval.TICK],
        help="K 线周期",
    )
    parser.add_argument("--start", required=True, help="开始日期 YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="结束日期 YYYY-MM-DD")
    parser.add_argument(
        "--delay",
        type=float,
        default=0.3,
        help="每只标的之间的请求间隔（秒），避免触发限流",
    )
    parser.add_argument(
        "--symbols",
        nargs="*",
        help="仅下载指定代码（可选，如 600000 600519）",
    )
    return parser.parse_args()


def main() -> None:
    load_dotenv(ENV_FILE)
    args = parse_args()

    watchlist_path = Path(args.watchlist) if args.watchlist else None
    if watchlist_path is not None and not watchlist_path.exists():
        raise SystemExit(f"自选池文件不存在: {watchlist_path}")

    items = load_watchlist(watchlist_path)
    if args.symbols:
        symbol_set = set(args.symbols)
        items = [item for item in items if item.symbol in symbol_set]

    if not items:
        raise SystemExit("自选池为空，请通过 GUI/数据库维护自选，或使用 --watchlist 导入 CSV")

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


if __name__ == "__main__":
    main()
