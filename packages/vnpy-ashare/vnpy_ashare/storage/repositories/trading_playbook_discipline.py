"""Playbook 每日纪律 checklist repository。"""

from __future__ import annotations

from vnpy_ashare.domain.trading.playbook import DisciplineCheckItem
from vnpy_ashare.storage.connection import connect, init_app_db

DEFAULT_DISCIPLINE_CHECKS: tuple[tuple[str, str], ...] = (
    ("no_off_plan", "不在计划外开新仓"),
    ("morning_exit", "11:30 前评估上午必卖"),
    ("recession_flat", "退潮期不新开仓"),
    ("stop_first", "止损铁则优先于「再等等」"),
    ("no_intraday_rule_change", "盘中不改规则，复盘后再改"),
)


def list_discipline_check_defs() -> tuple[tuple[str, str], ...]:
    return DEFAULT_DISCIPLINE_CHECKS


def load_discipline_checks(trade_date: str) -> tuple[DisciplineCheckItem, ...]:
    day = trade_date[:10]
    init_app_db()
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT check_id, checked
            FROM trading_playbook_discipline_daily
            WHERE trade_date = ?
            """,
            (day,),
        ).fetchall()
    checked_map = {str(row["check_id"]): bool(row["checked"]) for row in rows}
    return tuple(DisciplineCheckItem(check_id=check_id, label=label, checked=checked_map.get(check_id, False)) for check_id, label in DEFAULT_DISCIPLINE_CHECKS)


def set_discipline_check(trade_date: str, check_id: str, checked: bool) -> None:
    day = trade_date[:10]
    init_app_db()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO trading_playbook_discipline_daily (trade_date, check_id, checked)
            VALUES (?, ?, ?)
            ON CONFLICT(trade_date, check_id) DO UPDATE SET checked = excluded.checked
            """,
            (day, check_id, int(checked)),
        )
