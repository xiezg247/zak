"""Playbook 纪律与计划外检测测试。"""

from __future__ import annotations

from vnpy.trader.constant import Exchange

from vnpy_ashare.storage.repositories.positions import add_position_item
from vnpy_ashare.storage.repositories.trading_plans import create_trading_plan
from vnpy_ashare.storage.repositories.trading_playbook_discipline import (
    load_discipline_checks,
    set_discipline_check,
)
from vnpy_ashare.storage.repositories.watchlist import add_watchlist_item
from vnpy_ashare.trading.journal.off_plan_scan import list_off_plan_position_vt_symbols


def test_discipline_checks_reset_by_trade_date(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "zak.db"
    monkeypatch.setattr("vnpy_ashare.storage.connection.get_app_db_path", lambda: db_path)

    items = load_discipline_checks("2026-06-23")
    assert len(items) == 5
    assert all(not item.checked for item in items)

    set_discipline_check("2026-06-23", "no_off_plan", True)
    checked = load_discipline_checks("2026-06-23")
    assert next(item for item in checked if item.check_id == "no_off_plan").checked is True

    fresh = load_discipline_checks("2026-06-24")
    assert all(not item.checked for item in fresh)


def test_off_plan_positions(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "zak.db"
    monkeypatch.setattr("vnpy_ashare.storage.connection.get_app_db_path", lambda: db_path)
    monkeypatch.setattr("vnpy_ashare.trading.journal.off_plan_scan.today_trade_date", lambda: "2026-06-23")

    add_watchlist_item("600000", Exchange.SSE, name="浦发")
    add_watchlist_item("000001", Exchange.SZSE, name="平安")
    assert add_position_item("600000", Exchange.SSE, cost_price=10.0, volume=100, buy_date="2026-06-22")
    assert add_position_item("000001", Exchange.SZSE, cost_price=10.0, volume=100, buy_date="2026-06-22")

    plan_id = create_trading_plan(
        trade_date="2026-06-23",
        status="active",
        symbols=[("600000", Exchange.SSE)],
    )
    assert plan_id

    off_plan = list_off_plan_position_vt_symbols(trade_date="2026-06-23")
    assert off_plan == ("000001.SZSE",)
