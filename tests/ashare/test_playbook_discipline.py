"""Playbook 纪律与计划外检测测试。"""

from __future__ import annotations

import uuid

from vnpy.trader.constant import Exchange

from vnpy_ashare.storage.repositories.positions import add_position_item
from vnpy_ashare.storage.repositories.trading_plans import create_trading_plan
from vnpy_ashare.storage.repositories.trading_playbook_discipline import (
    load_discipline_checks,
    set_discipline_check,
)
from vnpy_ashare.storage.repositories.watchlist import add_watchlist_item
from vnpy_ashare.trading.plan.off_plan import list_off_plan_position_vt_symbols


def test_discipline_checks_reset_by_trade_date() -> None:
    seed = uuid.uuid4().hex
    trade_date = f"2099-01-{int(seed[:2], 16) % 28 + 1:02d}"
    other_date = f"2099-02-{int(seed[2:4], 16) % 28 + 1:02d}"
    items = load_discipline_checks(trade_date)
    assert len(items) == 5
    assert all(not item.checked for item in items)

    set_discipline_check(trade_date, "no_off_plan", True)
    checked = load_discipline_checks(trade_date)
    assert next(item for item in checked if item.check_id == "no_off_plan").checked is True

    fresh = load_discipline_checks(other_date)
    assert all(not item.checked for item in fresh)


def test_off_plan_positions(monkeypatch) -> None:
    trade_date = "2099-06-23"
    monkeypatch.setattr("vnpy_ashare.trading.plan.off_plan.today_trade_date", lambda: trade_date)

    suffix = uuid.uuid4().hex[:4]
    symbol_sse = f"60{suffix[:4]}"
    symbol_szse = f"00{suffix[:4]}"
    add_watchlist_item(symbol_sse, Exchange.SSE, name="浦发")
    add_watchlist_item(symbol_szse, Exchange.SZSE, name="平安")
    assert add_position_item(symbol_sse, Exchange.SSE, cost_price=10.0, volume=100, buy_date="2099-06-22")
    assert add_position_item(symbol_szse, Exchange.SZSE, cost_price=10.0, volume=100, buy_date="2099-06-22")

    plan_id = create_trading_plan(
        trade_date=trade_date,
        status="active",
        symbols=[(symbol_sse, Exchange.SSE)],
    )
    assert plan_id

    off_plan = list_off_plan_position_vt_symbols(trade_date=trade_date)
    assert f"{symbol_szse}.SZSE" in off_plan
    assert f"{symbol_sse}.SSE" not in off_plan
