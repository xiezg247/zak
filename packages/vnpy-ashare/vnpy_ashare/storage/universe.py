"""A 股全市场标的列表（TickFlow CN_Equity_A）"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from vnpy_ashare.domain.models import StockItem
from vnpy_ashare.integrations.tickflow.universe import fetch_universe_items
from vnpy_ashare.storage.app_db import (
    CACHE_MAX_AGE,
    init_app_db,
    load_universe_rows,
    save_universe_rows,
    universe_exists,
    universe_is_fresh,
)
from vnpy_common.paths import get_app_db_path


def sync_universe(force: bool = False) -> Path:
    """从 TickFlow 同步全 A 股标的列表到本地 SQLite"""
    init_app_db()
    if not force and universe_is_fresh(CACHE_MAX_AGE):
        return get_app_db_path()

    rows = fetch_universe_items()
    save_universe_rows(
        [(row.symbol, row.exchange, row.name) for row in rows],
        synced_at=datetime.now(),
    )
    return get_app_db_path()


def load_universe(*, allow_sync: bool = False) -> list[StockItem]:
    init_app_db()
    if not universe_exists():
        if allow_sync:
            sync_universe()
        else:
            raise FileNotFoundError("全 A 股列表不存在，请先点击「同步标的列表」或运行 scripts/sync_universe.py")

    return [StockItem(symbol=symbol, exchange=exchange, name=name) for symbol, exchange, name in load_universe_rows()]
