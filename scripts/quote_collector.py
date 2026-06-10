#!/usr/bin/env python3
"""全市场行情采集：TickFlow -> Redis。"""

from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime

from dotenv import load_dotenv

from vnpy_ashare.jobs import collect_market_quotes
from vnpy_ashare.market_hours import CHINA_TZ, is_ashare_trading_session, next_quotes_collect_at
from vnpy_common.paths import ENV_FILE
from vnpy_ashare.quotes.redis_store import RedisQuoteStore


def _sleep_until_next_collect(interval: int) -> None:
    now = datetime.now(CHINA_TZ)
    if is_ashare_trading_session(now):
        time.sleep(max(interval, 1))
        return

    target = next_quotes_collect_at(now, interval_seconds=max(interval, 1))
    delay = max(1.0, (target - now).total_seconds())
    print(f"非交易时段，休眠至 {target.strftime('%Y-%m-%d %H:%M:%S')}")
    time.sleep(delay)


def main() -> int:
    parser = argparse.ArgumentParser(description="采集全 A 股行情写入 Redis")
    parser.add_argument(
        "--interval",
        type=int,
        default=int(os.getenv("QUOTE_COLLECT_INTERVAL", "15")),
        help="交易时段内采集间隔（秒）",
    )
    parser.add_argument("--once", action="store_true", help="只采集一次后退出")
    args = parser.parse_args()

    load_dotenv(ENV_FILE)
    store = RedisQuoteStore()
    store.ping()
    interval = max(args.interval, 1)
    print(f"Redis 已连接，交易时段内采集间隔 {interval}s")

    while True:
        try:
            if not is_ashare_trading_session():
                if args.once:
                    print("非交易时段，跳过采集")
                    return 0
                _sleep_until_next_collect(interval)
                continue

            result = collect_market_quotes()
            print(result.message)
        except KeyboardInterrupt:
            print("已停止")
            return 0
        except Exception as ex:
            print(f"采集失败: {ex}", file=sys.stderr)

        if args.once:
            return 0
        _sleep_until_next_collect(interval)


if __name__ == "__main__":
    raise SystemExit(main())
