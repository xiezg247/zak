"""自选持仓 Service（投研层，非实盘 OMS）。"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from vnpy.trader.constant import Exchange

from vnpy_ashare.config.runtime import PRICE_TICK, normalize_volume
from vnpy_ashare.domain.time.market_hours import CHINA_TZ
from vnpy_ashare.domain.trading.position import PositionRecord
from vnpy_ashare.services.base import BaseService
from vnpy_ashare.storage.cache.watchlist_position_cache import WatchlistPositionDiskCache
from vnpy_ashare.storage.repositories.positions import (
    POSITION_MAX_ITEMS,
    add_position_item,
    clear_positions,
    load_position_row,
    load_position_rows,
    position_add_failure_reason,
    position_at_capacity,
    position_contains,
    position_item_count,
    remove_position_item,
    update_position_item,
)
from vnpy_ashare.storage.repositories.symbols import build_symbol_name_map
from vnpy_ashare.storage.repositories.watchlist import watchlist_contains

PositionAddFailure = Literal["duplicate", "full", "not_in_watchlist"]

_standalone_position_disk_cache: WatchlistPositionDiskCache | None = None


def get_position_disk_cache_standalone() -> WatchlistPositionDiskCache:
    global _standalone_position_disk_cache
    if _standalone_position_disk_cache is None:
        _standalone_position_disk_cache = WatchlistPositionDiskCache()
    return _standalone_position_disk_cache


def _row_float(value: str | float | int | None) -> float:
    if isinstance(value, bool):
        raise TypeError("invalid numeric field")
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        return float(value)
    raise TypeError("missing numeric field")


def _row_int(value: str | float | int | None) -> int:
    return int(_row_float(value))


def normalize_cost_price(cost_price: float) -> float:
    """成本价归一化为浮点，并按 A 股价档对齐。"""
    price = float(cost_price)
    if price <= 0:
        return price
    tick = PRICE_TICK
    return round(round(price / tick) * tick, 4)


class PositionService(BaseService):
    """自选页持仓记录。"""

    max_items = POSITION_MAX_ITEMS

    def get_items(self) -> list[PositionRecord]:
        name_map = build_symbol_name_map()
        records: list[PositionRecord] = []
        for row in load_position_rows():
            exchange = Exchange(str(row["exchange"]))
            symbol = str(row["symbol"])
            name = name_map.get((symbol, exchange), "")
            records.append(
                PositionRecord(
                    symbol=symbol,
                    exchange=exchange.value,
                    name=name,
                    cost_price=_row_float(row["cost_price"]),
                    volume=_row_int(row["volume"]),
                    buy_date=str(row["buy_date"]),
                    notes=str(row.get("notes") or ""),
                    source=str(row.get("source") or "manual"),  # type: ignore[arg-type]
                    plan_pct=row.get("plan_pct"),  # type: ignore[arg-type]
                )
            )
        return records

    def count(self) -> int:
        return position_item_count()

    def at_capacity(self) -> bool:
        return position_at_capacity()

    def contains(self, symbol: str, exchange: Exchange) -> bool:
        return position_contains(symbol, exchange)

    def add_failure_reason(self, symbol: str, exchange: Exchange) -> PositionAddFailure | None:
        return position_add_failure_reason(symbol, exchange)

    def validate_inputs(
        self,
        *,
        cost_price: float,
        volume: int,
        buy_date: str,
    ) -> str | None:
        if cost_price <= 0:
            return "成本价须大于 0"
        normalized = normalize_volume(volume)
        if normalized <= 0:
            return "持仓量须为 100 股整数倍"
        try:
            parsed = datetime.strptime(buy_date[:10], "%Y-%m-%d").date()
        except ValueError:
            return "买入日格式须为 YYYY-MM-DD"
        today = datetime.now(CHINA_TZ).date()
        if parsed > today:
            return "买入日不能晚于今日"
        return None

    def add(
        self,
        symbol: str,
        exchange: Exchange,
        *,
        cost_price: float,
        volume: int,
        buy_date: str,
        notes: str = "",
        plan_pct: float | None = None,
    ) -> bool:
        error = self.validate_inputs(cost_price=cost_price, volume=volume, buy_date=buy_date)
        if error is not None:
            return False
        if not watchlist_contains(symbol, exchange):
            return False
        return add_position_item(
            symbol,
            exchange,
            cost_price=normalize_cost_price(cost_price),
            volume=normalize_volume(volume),
            buy_date=buy_date[:10],
            notes=notes.strip(),
            plan_pct=plan_pct,
        )

    def update(
        self,
        symbol: str,
        exchange: Exchange,
        *,
        cost_price: float,
        volume: int,
        buy_date: str,
        notes: str = "",
        plan_pct: float | None = None,
        last_price: float | None = None,
    ) -> bool:
        del last_price
        error = self.validate_inputs(cost_price=cost_price, volume=volume, buy_date=buy_date)
        if error is not None:
            return False
        if load_position_row(symbol, exchange) is None:
            return False
        return update_position_item(
            symbol,
            exchange,
            cost_price=normalize_cost_price(cost_price),
            volume=normalize_volume(volume),
            buy_date=buy_date[:10],
            notes=notes.strip(),
            plan_pct=plan_pct,
        )

    def remove(self, symbol: str, exchange: Exchange) -> bool:
        if load_position_row(symbol, exchange) is None:
            return False
        return remove_position_item(symbol, exchange)

    def clear(self) -> None:
        clear_positions()

    def get_position_disk_cache(self) -> WatchlistPositionDiskCache:
        cache = getattr(self, "_position_disk_cache", None)
        if cache is None:
            cache = WatchlistPositionDiskCache()
            self._position_disk_cache = cache
        return cache
