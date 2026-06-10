"""A 股全市场标的列表（TickFlow CN_Equity_A）"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from tickflow import TickFlow

from vnpy_ashare.storage.app_db import (
    CACHE_MAX_AGE,
    init_app_db,
    load_universe_rows,
    save_universe_rows,
    universe_exists,
    universe_is_fresh,
)
from vnpy_ashare.domain.models import StockItem, parse_tickflow_symbol
from vnpy_common.paths import ENV_FILE, get_app_db_path

UNIVERSE_ID = "CN_Equity_A"
BATCH_SIZE = 200


def sync_universe(force: bool = False) -> Path:
    """从 TickFlow 同步全 A 股标的列表到本地 SQLite"""
    init_app_db()
    if not force and universe_is_fresh(CACHE_MAX_AGE):
        return get_app_db_path()

    load_dotenv(ENV_FILE)
    api_key = os.getenv("TICKFLOW_API_KEY", "")
    client = TickFlow(api_key=api_key) if api_key else TickFlow.free()

    universe = client.universes.get(UNIVERSE_ID)
    tf_symbols: list[str] = universe["symbols"]

    rows: list[StockItem] = []
    for start in range(0, len(tf_symbols), BATCH_SIZE):
        batch = tf_symbols[start : start + BATCH_SIZE]
        instruments = client.instruments.batch(batch)
        name_map = {item["symbol"]: item.get("name", "") for item in instruments}
        for tf_symbol in batch:
            item = parse_tickflow_symbol(tf_symbol, name_map.get(tf_symbol, ""))
            if item:
                rows.append(item)

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
