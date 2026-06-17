"""自选持仓记账 Service（投研层，非实盘 OMS）。"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from vnpy.trader.constant import Exchange

from vnpy_ashare.config import PRICE_TICK, normalize_volume
from vnpy_ashare.domain.market_hours import CHINA_TZ
from vnpy_ashare.domain.position_snapshot import PositionRecord
from vnpy_ashare.services.base import BaseService
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
    """自选页持仓记账。"""

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
        normalized_cost = normalize_cost_price(cost_price)
        normalized_volume = normalize_volume(volume)
        normalized_date = buy_date[:10]
        ok = add_position_item(
            symbol,
            exchange,
            cost_price=normalized_cost,
            volume=normalized_volume,
            buy_date=normalized_date,
            notes=notes.strip(),
            plan_pct=plan_pct,
        )
        if ok:
            self._record_buy_journal(
                symbol,
                exchange,
                cost_price=normalized_cost,
                volume=normalized_volume,
                buy_date=normalized_date,
            )
        return ok

    def _record_buy_journal(
        self,
        symbol: str,
        exchange: Exchange,
        *,
        cost_price: float,
        volume: int,
        buy_date: str,
    ) -> None:
        from vnpy_ashare.trading.journal.record_buy import record_buy_from_position

        record_buy_from_position(
            symbol,
            exchange,
            cost_price=normalize_cost_price(cost_price),
            volume=normalize_volume(volume),
            buy_date=buy_date[:10],
            notify_engine=self.engine,
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
        error = self.validate_inputs(cost_price=cost_price, volume=volume, buy_date=buy_date)
        if error is not None:
            return False
        existing_row = load_position_row(symbol, exchange)
        if existing_row is None:
            return False
        old_volume = _row_int(existing_row["volume"])
        normalized_cost = normalize_cost_price(cost_price)
        normalized_volume = normalize_volume(volume)
        normalized_date = buy_date[:10]
        ok = update_position_item(
            symbol,
            exchange,
            cost_price=normalized_cost,
            volume=normalized_volume,
            buy_date=normalized_date,
            notes=notes.strip(),
            plan_pct=plan_pct,
        )
        if ok and normalized_volume > old_volume:
            from vnpy_ashare.domain.position_snapshot import PositionRecord
            from vnpy_ashare.trading.journal.record_add import (
                record_volume_increase_buy,
                should_tag_add_loss,
            )

            record = PositionRecord(
                symbol=symbol,
                exchange=exchange.value,
                name="",
                cost_price=_row_float(existing_row["cost_price"]),
                volume=old_volume,
                buy_date=str(existing_row["buy_date"]),
            )
            add_loss = should_tag_add_loss(record, new_volume=normalized_volume, last_price=last_price)
            record_volume_increase_buy(
                symbol,
                exchange,
                cost_price=normalized_cost,
                delta_volume=normalized_volume - old_volume,
                buy_date=normalized_date,
                add_loss=add_loss,
                notify_engine=self.engine,
            )
        return ok

    def remove(
        self,
        symbol: str,
        exchange: Exchange,
        *,
        sell_price: float | None = None,
        sell_date: str | None = None,
        reason: str = "",
    ) -> bool:
        row = load_position_row(symbol, exchange)
        if row is None:
            return False
        cost_price = _row_float(row["cost_price"])
        volume = _row_int(row["volume"])
        price = sell_price if sell_price is not None and sell_price > 0 else cost_price
        ok = remove_position_item(symbol, exchange)
        if ok:
            self._record_sell_journal(
                symbol,
                exchange,
                cost_price=cost_price,
                volume=volume,
                sell_price=price,
                sell_date=sell_date,
                reason=reason,
            )
        return ok

    def clear(
        self,
        *,
        sell_prices: dict[tuple[str, str], float] | None = None,
        sell_date: str | None = None,
    ) -> None:
        rows = load_position_rows()
        clear_positions()
        for row in rows:
            symbol = str(row["symbol"])
            exchange_name = str(row["exchange"])
            try:
                exchange = Exchange(exchange_name)
            except ValueError:
                continue
            key = (symbol, exchange_name)
            cost_price = _row_float(row["cost_price"])
            sell_price = (sell_prices or {}).get(key, cost_price)
            self._record_sell_journal(
                symbol,
                exchange,
                cost_price=cost_price,
                volume=_row_int(row["volume"]),
                sell_price=sell_price,
                sell_date=sell_date,
                reason="批量清仓",
            )

    def _record_sell_journal(
        self,
        symbol: str,
        exchange: Exchange,
        *,
        cost_price: float,
        volume: int,
        sell_price: float,
        sell_date: str | None,
        reason: str,
    ) -> None:
        from vnpy_ashare.trading.journal.record_sell import record_sell_from_position

        record_sell_from_position(
            symbol,
            exchange,
            cost_price=cost_price,
            volume=volume,
            sell_price=sell_price,
            sell_date=sell_date,
            reason=reason,
        )
