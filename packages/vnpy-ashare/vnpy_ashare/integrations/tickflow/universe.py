"""从 TickFlow 拉取全 A 股标的列表。"""

from __future__ import annotations

from vnpy_ashare.domain.symbols import StockItem, parse_tickflow_symbol
from vnpy_tickflow.client import get_tickflow_client

UNIVERSE_ID = "CN_Equity_A"
BATCH_SIZE = 200


def fetch_universe_items(*, universe_id: str = UNIVERSE_ID) -> list[StockItem]:
    """从 TickFlow universe 批量拉取 A 股标的。"""
    client = get_tickflow_client()
    universe = client.universes.get(universe_id)
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
    return rows
