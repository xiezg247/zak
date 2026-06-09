#!/usr/bin/env python3
"""检查 VeighNa 数据库连接（SQLite / PostgreSQL）。"""

from __future__ import annotations

from vnpy.trader.database import get_database
from vnpy.trader.setting import SETTINGS


def main() -> None:
    name = SETTINGS.get("database.name", "sqlite")
    print(f"database.name = {name}")

    if name == "postgresql":
        print(f"  host={SETTINGS.get('database.host')} port={SETTINGS.get('database.port')}")

    db = get_database()
    overviews = db.get_bar_overview()
    print(f"连接成功，本地日 K 概览 {len(overviews)} 条")


if __name__ == "__main__":
    main()
