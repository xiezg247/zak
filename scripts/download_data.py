#!/usr/bin/env python3
"""命令行下载单只标的 K 线到本地 SQLite 数据库"""

from __future__ import annotations

import argparse
from datetime import datetime

from dotenv import load_dotenv
from vnpy.trader.constant import Exchange, Interval

from vnpy_ashare.bars import default_minute_download_start, download_bars, download_period_bars
from vnpy_ashare.minute_periods import MINUTE_PERIODS
from vnpy_ashare.paths import ENV_FILE


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="下载历史 K 线到本地数据库")
    parser.add_argument("--symbol", required=True, help="合约代码，如 600000")
    parser.add_argument(
        "--exchange",
        required=True,
        choices=[item.name for item in Exchange],
        help="交易所，如 SSE",
    )
    parser.add_argument(
        "--interval",
        default="DAILY",
        choices=[item.name for item in Interval if item != Interval.TICK],
        help="K 线周期（日K/小时K/分钟K）",
    )
    parser.add_argument(
        "--period",
        choices=list(MINUTE_PERIODS),
        help="分K周期（仅 1m）；指定后覆盖 --interval 的分钟映射",
    )
    parser.add_argument("--start", help="开始日期 YYYY-MM-DD（分K默认近6个月）")
    parser.add_argument("--end", help="结束日期 YYYY-MM-DD（默认今天）")
    return parser.parse_args()


def main() -> None:
    load_dotenv(ENV_FILE)
    args = parse_args()
    exchange = Exchange[args.exchange]
    end = datetime.strptime(args.end, "%Y-%m-%d") if args.end else datetime.now()

    if args.period:
        start = (
            datetime.strptime(args.start, "%Y-%m-%d")
            if args.start
            else default_minute_download_start(end)
        )
        count = download_period_bars(
            symbol=args.symbol,
            exchange=exchange,
            period=args.period,
            start=start,
            end=end,
        )
        print(f"已保存 {count} 根 {args.period} K 线: {args.symbol}.{args.exchange}")
        return

    if not args.start:
        raise SystemExit("日K/小时K 下载需指定 --start")
    start = datetime.strptime(args.start, "%Y-%m-%d")

    count = download_bars(
        symbol=args.symbol,
        exchange=exchange,
        interval=Interval[args.interval],
        start=start,
        end=end,
    )
    print(f"已保存 {count} 根 K 线: {args.symbol}.{args.exchange}")


if __name__ == "__main__":
    main()
