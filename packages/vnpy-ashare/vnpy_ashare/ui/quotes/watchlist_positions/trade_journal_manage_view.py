"""交易流水明细：查看 / 编辑 / 删除。"""

from __future__ import annotations

from datetime import datetime, timedelta

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.domain.time.market_hours import CHINA_TZ
from vnpy_ashare.domain.trading.journal import TradeJournalEntry
from vnpy_ashare.storage.repositories.trade_journal import get_trade_journal_entry, query_trade_journal
from vnpy_ashare.trading.journal.maintain import delete_journal_entry
from vnpy_ashare.ui.quotes.watchlist_positions.trade_journal_edit_dialog import TradeJournalEditDialog

_ENTRY_ID_ROLE = QtCore.Qt.ItemDataRole.UserRole
_SIDE_LABELS = {"buy": "买入", "sell": "卖出", "hold": "观望"}
_SIDE_FILTER_OPTIONS: tuple[tuple[str, str | None], ...] = (
    ("全部", None),
    ("买入", "buy"),
    ("卖出", "sell"),
    ("观望", "hold"),
)


class TradeJournalManageView(QtWidgets.QWidget):
    """可嵌入复盘对话框或笔记中心的流水明细表。"""

    entries_changed = QtCore.Signal()

    def __init__(
        self,
        parent: QtWidgets.QWidget | None = None,
        *,
        show_range_controls: bool = True,
        initial_days: int = 7,
        initial_side: str | None = None,
    ) -> None:
        super().__init__(parent)
        self._show_range_controls = show_range_controls
        self._fixed_start: str | None = None
        self._fixed_end: str | None = None
        self._symbol_filter = ""
        self._exchange_filter = ""
        self._days_spin: QtWidgets.QSpinBox | None
        self._side_combo: QtWidgets.QComboBox | None

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        if show_range_controls:
            range_row = QtWidgets.QHBoxLayout()
            self._days_spin = QtWidgets.QSpinBox(self)
            self._days_spin.setRange(1, 365)
            self._days_spin.setValue(max(1, initial_days))
            self._days_spin.setSuffix(" 天")
            self._side_combo = QtWidgets.QComboBox(self)
            for label, value in _SIDE_FILTER_OPTIONS:
                self._side_combo.addItem(label, value)
            if initial_side:
                for index in range(self._side_combo.count()):
                    if self._side_combo.itemData(index) == initial_side:
                        self._side_combo.setCurrentIndex(index)
                        break
            refresh_btn = QtWidgets.QPushButton("刷新", self)
            refresh_btn.clicked.connect(self.reload)
            range_row.addWidget(QtWidgets.QLabel("区间", self))
            range_row.addWidget(self._days_spin)
            range_row.addWidget(QtWidgets.QLabel("方向", self))
            range_row.addWidget(self._side_combo)
            range_row.addWidget(refresh_btn)
            range_row.addStretch(1)
            layout.addLayout(range_row)
        else:
            self._days_spin = None
            self._side_combo = None

        self._summary = QtWidgets.QLabel("", self)
        self._summary.setObjectName("SettingsHint")
        self._summary.setWordWrap(True)
        layout.addWidget(self._summary)

        self._table = QtWidgets.QTableWidget(self)
        self._table.setColumnCount(8)
        self._table.setHorizontalHeaderLabels(
            ["成交日", "标的", "方向", "价格", "数量", "盈亏", "计划", "理由"],
        )
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._show_context_menu)
        self._table.doubleClicked.connect(self._edit_selected)
        layout.addWidget(self._table, stretch=1)

        action_row = QtWidgets.QHBoxLayout()
        self._edit_button = QtWidgets.QPushButton("编辑…", self)
        self._edit_button.setObjectName("SecondaryButton")
        self._edit_button.clicked.connect(self._edit_selected)
        self._delete_button = QtWidgets.QPushButton("删除", self)
        self._delete_button.setObjectName("SecondaryButton")
        self._delete_button.clicked.connect(self._delete_selected)
        action_row.addWidget(self._edit_button)
        action_row.addWidget(self._delete_button)
        action_row.addStretch(1)
        layout.addLayout(action_row)

        self.reload()

    def set_date_range(self, *, start_date: str, end_date: str) -> None:
        self._fixed_start = start_date[:10]
        self._fixed_end = end_date[:10]
        if self._days_spin is not None:
            self._days_spin.setEnabled(False)

    def set_side_filter(self, side: str | None) -> None:
        if self._side_combo is None:
            return
        for index in range(self._side_combo.count()):
            if self._side_combo.itemData(index) == side:
                self._side_combo.setCurrentIndex(index)
                break

    def set_symbol_filter(self, *, symbol: str = "", exchange: str = "") -> None:
        self._symbol_filter = symbol.strip()
        self._exchange_filter = exchange.strip()

    def reload(self) -> None:
        start, end = self._resolve_date_range()
        side = self._resolve_side_filter()
        entries = query_trade_journal(
            start_date=start,
            end_date=end,
            side=side,
            symbol=self._symbol_filter or None,
            exchange=self._exchange_filter or None,
            limit=2000,
        )
        self._render_entries(entries, start=start, end=end)

    def _resolve_date_range(self) -> tuple[str, str]:
        if self._fixed_start and self._fixed_end:
            return self._fixed_start, self._fixed_end
        end = datetime.now(CHINA_TZ).date()
        days = int(self._days_spin.value()) if self._days_spin is not None else 7
        start = end - timedelta(days=max(1, days) - 1)
        return start.isoformat(), end.isoformat()

    def _resolve_side_filter(self) -> str | None:
        if self._side_combo is None:
            return None
        value = self._side_combo.currentData()
        return str(value) if value else None

    def _render_entries(self, entries: list[TradeJournalEntry], *, start: str, end: str) -> None:
        sell_pnl = sum(item.pnl for item in entries if item.side == "sell" and item.pnl is not None)
        self._summary.setText(
            f"{start} ~ {end} · 共 {len(entries)} 条" + (f" · 卖出已实现 {sell_pnl:+.2f} 元" if sell_pnl else ""),
        )
        self._table.setRowCount(len(entries))
        for row_index, entry in enumerate(entries):
            self._table.setItem(row_index, 0, QtWidgets.QTableWidgetItem(entry.trade_date))
            self._table.setItem(row_index, 1, QtWidgets.QTableWidgetItem(entry.vt_symbol))
            self._table.setItem(
                row_index,
                2,
                QtWidgets.QTableWidgetItem(_SIDE_LABELS.get(entry.side, entry.side)),
            )
            self._table.setItem(row_index, 3, QtWidgets.QTableWidgetItem(f"{entry.price:.3f}"))
            self._table.setItem(row_index, 4, QtWidgets.QTableWidgetItem(str(entry.volume)))
            pnl_text = "—"
            if entry.pnl is not None:
                pnl_text = f"{entry.pnl:+.2f}"
                if entry.pnl_pct is not None:
                    pnl_text += f" ({entry.pnl_pct:+.1f}%)"
            self._table.setItem(row_index, 5, QtWidgets.QTableWidgetItem(pnl_text))
            plan_text = "是" if entry.on_plan else "否"
            if entry.violation_tags:
                plan_text += " · " + ",".join(entry.violation_tags)
            self._table.setItem(row_index, 6, QtWidgets.QTableWidgetItem(plan_text))
            reason = entry.reason or entry.mode or "—"
            self._table.setItem(row_index, 7, QtWidgets.QTableWidgetItem(reason))
            id_item = self._table.item(row_index, 0)
            if id_item is not None:
                id_item.setData(_ENTRY_ID_ROLE, int(entry.id))

    def _entry_id_for_row(self, row: int) -> int | None:
        if row < 0:
            return None
        item = self._table.item(row, 0)
        if item is None:
            return None
        value = item.data(_ENTRY_ID_ROLE)
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _selected_entry_id(self) -> int | None:
        return self._entry_id_for_row(self._table.currentRow())

    def _edit_selected(self) -> None:
        entry_id = self._selected_entry_id()
        if entry_id is None:
            return
        entry = get_trade_journal_entry(entry_id)
        if entry is None:
            return
        if TradeJournalEditDialog.edit_entry(entry, parent=self):
            self.reload()
            self.entries_changed.emit()

    def _delete_selected(self) -> None:
        entry_id = self._selected_entry_id()
        if entry_id is None:
            QtWidgets.QMessageBox.information(self, "删除流水", "请先选中一条流水。")
            return
        entry = get_trade_journal_entry(entry_id)
        if entry is None:
            QtWidgets.QMessageBox.warning(self, "删除流水", "未找到该条流水，请刷新后重试。")
            return
        answer = QtWidgets.QMessageBox.question(
            self,
            "删除流水",
            f"确定删除 {entry.vt_symbol} {entry.trade_date} 的{_SIDE_LABELS.get(entry.side, entry.side)}记录？\n可能影响风控闸当日盈亏与扛单检测。",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No,
        )
        if answer != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        if delete_journal_entry(entry_id):
            self.reload()
            self.entries_changed.emit()
            return
        QtWidgets.QMessageBox.warning(self, "删除流水", "删除失败，请重试。")

    def _show_context_menu(self, pos: QtCore.QPoint) -> None:
        row = self._table.rowAt(pos.y())
        if row < 0:
            return
        self._table.selectRow(row)
        if self._entry_id_for_row(row) is None:
            return
        menu = QtWidgets.QMenu(self)
        edit_action = menu.addAction("编辑…")
        edit_action.triggered.connect(self._edit_selected)
        delete_action = menu.addAction("删除")
        delete_action.triggered.connect(self._delete_selected)
        menu.popup(self._table.viewport().mapToGlobal(pos))
