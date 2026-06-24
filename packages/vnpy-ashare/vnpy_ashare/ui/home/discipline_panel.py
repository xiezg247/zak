"""Playbook §5 每日纪律 checklist。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.domain.trading.playbook import DisciplineCheckItem
from vnpy_ashare.services.trading_playbook import save_discipline_check
from vnpy_ashare.trading.risk.realized_pnl import today_trade_date


class PlaybookDisciplinePanel(QtWidgets.QWidget):
    changed = QtCore.Signal()

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("HomeDisciplinePanel")
        self._layout = QtWidgets.QVBoxLayout(self)
        self._layout.setContentsMargins(0, 4, 0, 4)
        self._layout.setSpacing(4)
        self._checks: list[QtWidgets.QCheckBox] = []
        self._off_plan_label = QtWidgets.QLabel("")
        self._off_plan_label.setObjectName("HomeAlert")
        self._off_plan_label.setWordWrap(True)
        self._off_plan_label.hide()
        self._layout.addWidget(self._off_plan_label)

    def apply(
        self,
        items: tuple[DisciplineCheckItem, ...],
        *,
        off_plan_symbols: tuple[str, ...] = (),
    ) -> None:
        while self._layout.count() > 1:
            item = self._layout.takeAt(1)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._checks.clear()

        for check in items:
            box = QtWidgets.QCheckBox(check.label)
            box.setObjectName("HomeDisciplineCheck")
            box.setChecked(check.checked)
            box.toggled.connect(lambda checked, cid=check.check_id: self._on_toggle(cid, checked))
            self._checks.append(box)
            self._layout.addWidget(box)

        if off_plan_symbols:
            joined = "、".join(off_plan_symbols)
            self._off_plan_label.setText(f"计划外持仓：{joined}")
            self._off_plan_label.setProperty("severity", "danger")
            self._off_plan_label.style().unpolish(self._off_plan_label)
            self._off_plan_label.style().polish(self._off_plan_label)
            self._off_plan_label.show()
        else:
            self._off_plan_label.hide()
            self._off_plan_label.setProperty("severity", "")

    def _on_toggle(self, check_id: str, checked: bool) -> None:
        save_discipline_check(today_trade_date(), check_id, checked)
        self.changed.emit()
