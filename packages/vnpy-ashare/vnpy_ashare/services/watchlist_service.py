"""自选池 CRUD Service。"""

from __future__ import annotations

from vnpy.trader.constant import Exchange

from vnpy_ashare.app_db import (
    add_watchlist_item,
    load_watchlist_rows,
    move_watchlist_item,
    remove_watchlist_item,
)
from vnpy_ashare.services.base import BaseService


class WatchlistService(BaseService):
    """自选池管理。"""

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

    def add(self, symbol: str, exchange: Exchange, name: str = "") -> bool:
        return add_watchlist_item(symbol, exchange, name)

    def remove(self, symbol: str, exchange: Exchange) -> bool:
        return remove_watchlist_item(symbol, exchange)

    def move(self, symbol: str, exchange: Exchange, direction: str) -> bool:
        return move_watchlist_item(symbol, exchange, direction=direction)
