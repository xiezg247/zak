#!/usr/bin/env python3
"""同步 TickFlow 全 A 股标的列表到本地 SQLite"""

from __future__ import annotations

from vnpy_ashare.app_db import universe_count
from vnpy_common.paths import get_app_db_path
from vnpy_ashare.universe import sync_universe


def main() -> None:
    sync_universe(force=True)
    count = universe_count()
    print(f"已同步 {count} 只 A 股到 {get_app_db_path()}")


if __name__ == "__main__":
    main()
