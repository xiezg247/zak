"""流水 Tab：列表 + 追加输入。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtGui, QtWidgets

from vnpy_ashare.domain.models.stock_note import StockNoteEntry
from vnpy_common.ui.theme.manager import theme_manager

_ENTRY_ID_ROLE = QtCore.Qt.ItemDataRole.UserRole


class StockNoteJournalTab(QtWidgets.QWidget):
    entry_submitted = QtCore.Signal(str)
    entry_delete_requested = QtCore.Signal(int)
    entry_import_requested = QtCore.Signal(int)
    ai_polish_requested = QtCore.Signal()

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("StockNoteJournalTab")

        self._list = QtWidgets.QListWidget(self)
        self._list.setObjectName("StockNoteJournalList")
        self._list.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self._list.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self._list.customContextMenuRequested.connect(self._show_context_menu)

        self._input = QtWidgets.QPlainTextEdit(self)
        self._input.setObjectName("StockNoteJournalInput")
        self._input.setPlaceholderText("随手记一笔…（Ctrl+Enter 保存）")
        self._input.setMaximumHeight(56)

        self._attach_quote = QtWidgets.QCheckBox("附带行情", self)
        self._attach_quote.setChecked(True)

        self._ai_button = QtWidgets.QPushButton("AI 整理", self)
        self._ai_button.setObjectName("SecondaryButton")
        self._ai_button.setToolTip("用 AI 整理输入框内容（不自动保存）")
        self._ai_button.clicked.connect(self.ai_polish_requested.emit)

        self._add_button = QtWidgets.QPushButton("添加", self)
        self._add_button.setObjectName("SecondaryButton")
        self._add_button.clicked.connect(self._submit)

        input_row = QtWidgets.QHBoxLayout()
        input_row.setSpacing(6)
        input_row.addWidget(self._input, stretch=1)
        input_row.addWidget(self._attach_quote)
        input_row.addWidget(self._ai_button)
        input_row.addWidget(self._add_button)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(self._list, stretch=1)
        layout.addLayout(input_row)

        shortcut = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+Return"), self._input)
        shortcut.activated.connect(self._submit)

        theme_manager().bind_stylesheet(self)

    def attach_quote_enabled(self) -> bool:
        return self._attach_quote.isChecked()

    def input_text(self) -> str:
        return self._input.toPlainText()

    def set_input_text(self, text: str) -> None:
        self._input.setPlainText(text)

    def set_ai_busy(self, busy: bool) -> None:
        self._ai_button.setEnabled(not busy)
        self._add_button.setEnabled(not busy)
        self._input.setEnabled(not busy)
        if busy:
            self._ai_button.setText("整理中…")
        else:
            self._ai_button.setText("AI 整理")

    def load_entries(self, entries: list[StockNoteEntry]) -> None:
        self._list.clear()
        for entry in entries:
            self._list.addItem(_make_list_item(entry))

    def clear(self) -> None:
        self._list.clear()
        self._input.clear()

    def focus_input(self) -> None:
        self._input.setFocus(QtCore.Qt.FocusReason.OtherFocusReason)

    def remove_entry_id(self, entry_id: int) -> None:
        for index in range(self._list.count()):
            item = self._list.item(index)
            if item is not None and item.data(_ENTRY_ID_ROLE) == entry_id:
                self._list.takeItem(index)
                break

    def _submit(self) -> None:
        text = self._input.toPlainText().strip()
        if not text:
            return
        self.entry_submitted.emit(text)
        self._input.clear()

    def prepend_entry(self, entry: StockNoteEntry) -> None:
        self._list.insertItem(0, _make_list_item(entry))

    def _show_context_menu(self, pos: QtCore.QPoint) -> None:
        item = self._list.itemAt(pos)
        if item is None:
            return
        entry_id = item.data(_ENTRY_ID_ROLE)
        if entry_id is None:
            return
        menu = QtWidgets.QMenu(self)
        import_action = menu.addAction("导入交易流水")
        import_action.triggered.connect(lambda: self.entry_import_requested.emit(int(entry_id)))
        delete_action = menu.addAction("删除此条")
        delete_action.triggered.connect(lambda: self.entry_delete_requested.emit(int(entry_id)))
        menu.popup(self._list.viewport().mapToGlobal(pos))


def _make_list_item(entry: StockNoteEntry) -> QtWidgets.QListWidgetItem:
    item = QtWidgets.QListWidgetItem(_format_list_item(entry))
    item.setData(_ENTRY_ID_ROLE, entry.id)
    return item


def _format_list_item(entry: StockNoteEntry) -> str:
    time_label = _format_entry_time(entry.created_at)
    return f"{time_label}  {entry.body}"


def _format_entry_time(created_at: str) -> str:
    text = created_at.strip()
    if "T" in text:
        return text.split("T", 1)[1][:5]
    if " " in text:
        return text.split(" ", 1)[1][:5]
    return text[:5]
