"""编辑单条交易流水。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.domain.trading.journal import TradeJournalEntry
from vnpy_ashare.trading.journal.maintain import update_journal_entry

_SIDE_LABELS = {"buy": "买入", "sell": "卖出", "hold": "观望"}
_VIOLATION_OPTIONS = ("off_plan", "recession_buy", "add_loss", "float_loss_hold")


def _localize_dialog_buttons(box: QtWidgets.QDialogButtonBox) -> None:
    ok_btn = box.button(QtWidgets.QDialogButtonBox.StandardButton.Ok)
    if ok_btn is not None:
        ok_btn.setText("确定")
    cancel_btn = box.button(QtWidgets.QDialogButtonBox.StandardButton.Cancel)
    if cancel_btn is not None:
        cancel_btn.setText("取消")


class TradeJournalEditDialog(QtWidgets.QDialog):
    def __init__(self, entry: TradeJournalEntry, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._entry = entry
        self.setWindowTitle("编辑流水")
        self.setMinimumWidth(380)

        layout = QtWidgets.QFormLayout(self)
        side_label = _SIDE_LABELS.get(entry.side, entry.side)
        layout.addRow("标的", QtWidgets.QLabel(f"{entry.symbol}.{entry.exchange}  ·  {side_label}", self))

        self._date_edit = QtWidgets.QDateEdit(self)
        self._date_edit.setCalendarPopup(True)
        self._date_edit.setDisplayFormat("yyyy-MM-dd")
        parts = entry.trade_date.split("-")
        if len(parts) == 3:
            self._date_edit.setDate(QtCore.QDate(int(parts[0]), int(parts[1]), int(parts[2])))
        layout.addRow("成交日", self._date_edit)

        self._price_spin = QtWidgets.QDoubleSpinBox(self)
        self._price_spin.setRange(0.01, 999_999.0)
        self._price_spin.setDecimals(3)
        self._price_spin.setValue(entry.price)
        layout.addRow("价格", self._price_spin)

        self._volume_spin = QtWidgets.QSpinBox(self)
        self._volume_spin.setRange(1, 9_999_999)
        self._volume_spin.setValue(entry.volume)
        layout.addRow("数量", self._volume_spin)

        self._mode_edit = QtWidgets.QLineEdit(entry.mode, self)
        self._mode_edit.setPlaceholderText("limit_board / pullback / ultra_short …")
        layout.addRow("模式", self._mode_edit)

        self._on_plan = QtWidgets.QCheckBox("计划内", self)
        self._on_plan.setChecked(entry.on_plan)
        layout.addRow("", self._on_plan)

        tag_row = QtWidgets.QHBoxLayout()
        self._tag_checks: dict[str, QtWidgets.QCheckBox] = {}
        for tag in _VIOLATION_OPTIONS:
            box = QtWidgets.QCheckBox(tag, self)
            box.setChecked(tag in entry.violation_tags)
            self._tag_checks[tag] = box
            tag_row.addWidget(box)
        tag_row.addStretch(1)
        layout.addRow("违规标签", tag_row)

        self._reason_edit = QtWidgets.QPlainTextEdit(entry.reason, self)
        self._reason_edit.setMaximumHeight(72)
        layout.addRow("理由", self._reason_edit)

        if entry.side == "sell":
            pnl_text = "—" if entry.pnl is None else f"{entry.pnl:+.2f} 元"
            if entry.pnl_pct is not None:
                pnl_text += f"（{entry.pnl_pct:+.2f}%）"
            self._pnl_hint = QtWidgets.QLabel(f"当前盈亏：{pnl_text}；保存后按最近买入流水重算", self)
            self._pnl_hint.setObjectName("SettingsHint")
            self._pnl_hint.setWordWrap(True)
            layout.addRow("", self._pnl_hint)

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok | QtWidgets.QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        _localize_dialog_buttons(buttons)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def _on_accept(self) -> None:
        tags = tuple(tag for tag, box in self._tag_checks.items() if box.isChecked())
        updated = update_journal_entry(
            self._entry.id,
            trade_date=self._date_edit.date().toString("yyyy-MM-dd"),
            price=float(self._price_spin.value()),
            volume=int(self._volume_spin.value()),
            mode=self._mode_edit.text().strip(),
            on_plan=self._on_plan.isChecked(),
            violation_tags=tags,
            reason=self._reason_edit.toPlainText().strip(),
        )
        if updated is None:
            QtWidgets.QMessageBox.warning(self, "编辑失败", "未能更新该条流水。")
            return
        self.accept()

    @staticmethod
    def edit_entry(entry: TradeJournalEntry, parent: QtWidgets.QWidget | None = None) -> bool:
        dialog = TradeJournalEditDialog(entry, parent=parent)
        return dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted
