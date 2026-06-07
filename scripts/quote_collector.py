#!/usr/bin/env python3
"""全市场行情采集：TickFlow -> Redis。"""

from __future__ import annotations

import argparse
import os
import sys
import time

from dotenv import load_dotenv

from vnpy_ashare.jobs import collect_market_quotes
from vnpy_ashare.paths import ENV_FILE
from vnpy_ashare.quotes.redis_store import RedisQuoteStore


def main() -> int:
    parser = argparse.ArgumentParser(description="采集全 A 股行情写入 Redis")
    parser.add_argument(
        "--interval",
        type=int,
        default=int(os.getenv("QUOTE_COLLECT_INTERVAL", "15")),
        help="采集间隔（秒）",
    )
    parser.add_argument("--once", action="store_true", help="只采集一次后退出")
    args = parser.parse_args()

    load_dotenv(ENV_FILE)
    store = RedisQuoteStore()
    store.ping()
    print(f"Redis 已连接，采集间隔 {args.interval}s")

    while True:
        try:
            result = collect_market_quotes()
            print(result.message)
        except KeyboardInterrupt:
            print("已停止")
            return 0
        except Exception as ex:
            print(f"采集失败: {ex}", file=sys.stderr)

        if args.once:
            return 0
        time.sleep(max(args.interval, 1))


if __name__ == "__main__":
    raise SystemExit(main())
