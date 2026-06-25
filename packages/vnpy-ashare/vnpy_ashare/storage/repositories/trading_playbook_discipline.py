"""Playbook 每日纪律 checklist repository。"""

from __future__ import annotations

from sqlalchemy import delete, select

from vnpy_ashare.domain.trading.playbook import DisciplineCheckItem
from vnpy_ashare.storage.repository.app import AppUserScopedRepository
from vnpy_common.storage.tables import trading_playbook_discipline_daily as tpd

DEFAULT_DISCIPLINE_CHECKS: tuple[tuple[str, str], ...] = (
    ("no_off_plan", "不在计划外开新仓"),
    ("morning_exit", "11:30 前评估上午必卖"),
    ("recession_flat", "退潮期不新开仓"),
    ("stop_first", "止损铁则优先于「再等等」"),
    ("no_intraday_rule_change", "盘中不改规则，复盘后再改"),
)


class DisciplineRepository(AppUserScopedRepository):
    table = tpd

    def load_checks(self, trade_date: str) -> tuple[DisciplineCheckItem, ...]:
        day = trade_date[:10]
        rows = self.fetchall(
            select(tpd.c.check_id, tpd.c.checked).where(
                self.scope(tpd.c.trade_date == day)
            )
        )
        checked_map = {str(row["check_id"]): bool(row["checked"]) for row in rows}
        return tuple(
            DisciplineCheckItem(check_id=check_id, label=label, checked=checked_map.get(check_id, False))
            for check_id, label in DEFAULT_DISCIPLINE_CHECKS
        )

    def set_check(self, trade_date: str, check_id: str, checked: bool) -> None:
        day = trade_date[:10]

        def _write(conn) -> None:
            self.delete_where(
                conn,
                self.scope((tpd.c.trade_date == day) & (tpd.c.check_id == check_id)),
            )
            self.insert_for_user(
                conn,
                trade_date=day,
                check_id=check_id,
                checked=int(checked),
            )

        self.run(_write)


_repo = DisciplineRepository()


def list_discipline_check_defs() -> tuple[tuple[str, str], ...]:
    return DEFAULT_DISCIPLINE_CHECKS


def load_discipline_checks(trade_date: str) -> tuple[DisciplineCheckItem, ...]:
    return _repo.load_checks(trade_date)


def set_discipline_check(trade_date: str, check_id: str, checked: bool) -> None:
    _repo.set_check(trade_date, check_id, checked)
