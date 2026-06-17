"""自选池 CRUD Service。"""

from __future__ import annotations

from typing import Literal

from vnpy.trader.constant import Exchange

from vnpy_ashare.services.base import BaseService
from vnpy_ashare.storage.repositories.watchlist import (
    WATCHLIST_MAX_ITEMS,
    add_watchlist_item,
    load_watchlist_rows,
    move_watchlist_item,
    remove_watchlist_item,
    watchlist_add_failure_reason,
    watchlist_at_capacity,
    watchlist_item_count,
)
from vnpy_ashare.storage.repositories.watchlist_groups import (
    WATCHLIST_MAX_GROUPS,
    WatchlistGroupRecord,
    add_watchlist_group_member,
    create_watchlist_group,
    delete_watchlist_group,
    load_watchlist_group_ids_for_item,
    load_watchlist_group_member_keys,
    load_watchlist_groups,
    remove_watchlist_group_member,
    rename_watchlist_group,
    set_watchlist_group_membership,
    update_watchlist_group_position_cap,
)

WatchlistAddFailure = Literal["duplicate", "full"]


class WatchlistService(BaseService):
    """自选池管理。"""

    max_items = WATCHLIST_MAX_ITEMS
    max_groups = WATCHLIST_MAX_GROUPS

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

    def move(self, symbol: str, exchange: Exchange, direction: Literal["up", "down"]) -> bool:
        return move_watchlist_item(symbol, exchange, direction=direction)

    def list_groups(self) -> list[WatchlistGroupRecord]:
        return load_watchlist_groups()

    def create_group(self, name: str) -> str | None:
        return create_watchlist_group(name)

    def rename_group(self, group_id: str, name: str) -> bool:
        return rename_watchlist_group(group_id, name)

    def delete_group(self, group_id: str) -> bool:
        return delete_watchlist_group(group_id)

    def add_to_group(self, group_id: str, symbol: str, exchange: Exchange) -> bool:
        return add_watchlist_group_member(group_id, symbol, exchange)

    def remove_from_group(self, group_id: str, symbol: str, exchange: Exchange) -> bool:
        return remove_watchlist_group_member(group_id, symbol, exchange)

    def group_ids_for_item(self, symbol: str, exchange: Exchange) -> set[str]:
        return load_watchlist_group_ids_for_item(symbol, exchange)

    def group_member_keys(self, group_id: str) -> set[tuple[str, str]]:
        return load_watchlist_group_member_keys(group_id)

    def set_item_groups(self, symbol: str, exchange: Exchange, group_ids: set[str]) -> None:
        set_watchlist_group_membership(symbol, exchange, group_ids)

    def set_group_position_cap(self, group_id: str, position_cap_pct: float | None) -> bool:
        return update_watchlist_group_position_cap(group_id, position_cap_pct)
