"""A 股全市场标的列表（TickFlow CN_Equity_A）"""

from __future__ import annotations

from datetime import datetime

from vnpy_ashare.domain.symbols.stock import StockItem
from vnpy_ashare.integrations.tickflow.universe import fetch_universe_items
from vnpy_ashare.storage.connection import init_app_db
from vnpy_ashare.storage.repositories.universe import (
    CACHE_MAX_AGE,
    count_universe,
    load_universe_rows,
    save_universe_rows,
    universe_exists,
    universe_is_fresh,
)


def sync_universe(force: bool = False) -> int:
    """从 TickFlow 同步全 A 股标的列表到 PostgreSQL，返回当前标的数量。"""
    init_app_db()
    if not force and universe_is_fresh(CACHE_MAX_AGE):
        return count_universe()

    rows = fetch_universe_items()
    save_universe_rows(
        [(row.symbol, row.exchange, row.name) for row in rows],
        synced_at=datetime.now(),
    )
    return count_universe()


def load_universe(*, allow_sync: bool = False) -> list[StockItem]:
    init_app_db()
    if not universe_exists():
        if allow_sync:
            sync_universe()
        else:
            raise FileNotFoundError("全 A 股列表不存在，请先点击「同步标的列表」或运行 cli.py job run sync_universe")

    return [StockItem(symbol=symbol, exchange=exchange, name=name) for symbol, exchange, name in load_universe_rows()]
