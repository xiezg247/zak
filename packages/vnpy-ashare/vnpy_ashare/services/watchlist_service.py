"""自选池 CRUD Service。"""

from __future__ import annotations

from typing import Literal

from vnpy.trader.constant import Exchange

from vnpy_ashare.services.base import BaseService
from vnpy_ashare.storage.app_db import (
    WATCHLIST_MAX_ITEMS,
    add_watchlist_item,
    load_watchlist_rows,
    move_watchlist_item,
    remove_watchlist_item,
    watchlist_add_failure_reason,
    watchlist_at_capacity,
    watchlist_item_count,
)

WatchlistAddFailure = Literal["duplicate", "full"]


class WatchlistService(BaseService):
    """自选池管理。"""

    max_items = WATCHLIST_MAX_ITEMS

    def get_items(self) -> list[dict[str, str]]:
        rows = load_watchlist_rows()
        return [
            {
                "symbol": symbol,
                "exchange": exchange.value,
                "name": name,
            }
            for symbol, exchange, name in rows
        ]

    def count(self) -> int:
        return watchlist_item_count()

    def at_capacity(self) -> bool:
        return watchlist_at_capacity()

    def add_failure_reason(self, symbol: str, exchange: Exchange) -> WatchlistAddFailure | None:
        return watchlist_add_failure_reason(symbol, exchange)

    def add(self, symbol: str, exchange: Exchange, name: str = "") -> bool:
        return add_watchlist_item(symbol, exchange, name)

    def remove(self, symbol: str, exchange: Exchange) -> bool:
        return remove_watchlist_item(symbol, exchange)

    def move(self, symbol: str, exchange: Exchange, direction: str) -> bool:
        return move_watchlist_item(symbol, exchange, direction=direction)
