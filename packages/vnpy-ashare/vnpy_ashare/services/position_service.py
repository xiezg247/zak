"""自选持仓记账 Service（投研层，非实盘 OMS）。"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from vnpy.trader.constant import Exchange

from vnpy_ashare.config import normalize_volume
from vnpy_ashare.domain.market_hours import CHINA_TZ
from vnpy_ashare.domain.position_snapshot import PositionRecord
from vnpy_ashare.services.base import BaseService
from vnpy_ashare.storage import app_db
from vnpy_ashare.storage.app_db import (
    POSITION_MAX_ITEMS,
    add_position_item,
    clear_positions,
    load_position_rows,
    position_add_failure_reason,
    position_at_capacity,
    position_contains,
    position_item_count,
    remove_position_item,
    update_position_item,
    watchlist_contains,
)

PositionAddFailure = Literal["duplicate", "full", "not_in_watchlist"]


class PositionService(BaseService):
    """自选页持仓记账。"""

    max_items = POSITION_MAX_ITEMS

    def get_items(self) -> list[PositionRecord]:
        name_map = app_db.build_symbol_name_map()
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
                    cost_price=float(row["cost_price"]),
                    volume=int(row["volume"]),
                    buy_date=str(row["buy_date"]),
                    notes=str(row.get("notes") or ""),
                    source=str(row.get("source") or "manual"),  # type: ignore[arg-type]
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
    ) -> bool:
        error = self.validate_inputs(cost_price=cost_price, volume=volume, buy_date=buy_date)
        if error is not None:
            return False
        if not watchlist_contains(symbol, exchange):
            return False
        return add_position_item(
            symbol,
            exchange,
            cost_price=round(cost_price, 2),
            volume=normalize_volume(volume),
            buy_date=buy_date[:10],
            notes=notes.strip(),
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
    ) -> bool:
        error = self.validate_inputs(cost_price=cost_price, volume=volume, buy_date=buy_date)
        if error is not None:
            return False
        return update_position_item(
            symbol,
            exchange,
            cost_price=round(cost_price, 2),
            volume=normalize_volume(volume),
            buy_date=buy_date[:10],
            notes=notes.strip(),
        )

    def remove(self, symbol: str, exchange: Exchange) -> bool:
        return remove_position_item(symbol, exchange)

    def clear(self) -> None:
        clear_positions()
