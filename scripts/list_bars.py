#!/usr/bin/env python3
"""查看自选池标的在本地数据库中的 K 线概况"""

from __future__ import annotations

from vnpy.trader.constant import Interval
from vnpy.trader.database import get_database

from vnpy_ashare.bars import load_watchlist


def main() -> None:
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
        print(f"{item.vt_symbol:<16} {item.name:<10} {row.count:>6}  {str(row.start.date()):<12} {str(row.end.date()):<12}")

    print("-" * 62)
    print(f"共 {len(items)} 只，已入库 {len(items) - missing} 只，缺失 {missing} 只")


if __name__ == "__main__":
    main()
