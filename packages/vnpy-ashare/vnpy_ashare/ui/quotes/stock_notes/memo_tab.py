"""备忘 Tab：防抖自动保存。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_common.ui.theme.manager import theme_manager

_DEBOUNCE_MS = 800


class StockNoteMemoTab(QtWidgets.QWidget):
    memo_changed = QtCore.Signal()
    ai_expand_requested = QtCore.Signal()

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("StockNoteMemoTab")
        self._dirty = False
        self._loading = False
        self._last_saved_body = ""

        toolbar = QtWidgets.QHBoxLayout()
        self._ai_button = QtWidgets.QPushButton("AI 扩写", self)
        self._ai_button.setObjectName("SecondaryButton")
        self._ai_button.setToolTip("扩写选中段落；未选中时扩写全文")
        self._ai_button.clicked.connect(self.ai_expand_requested.emit)
        toolbar.addWidget(self._ai_button)
        toolbar.addStretch()

        self._editor = QtWidgets.QPlainTextEdit(self)
        self._editor.setObjectName("StockNoteMemoEditor")
        self._editor.setPlaceholderText("研究逻辑、估值区间、关键事件…")
        self._editor.textChanged.connect(self._on_text_changed)

        self._status_label = QtWidgets.QLabel("", self)
        self._status_label.setObjectName("StockNoteStatus")

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addLayout(toolbar)
        layout.addWidget(self._editor, stretch=1)
        layout.addWidget(self._status_label)

        self._save_timer = QtCore.QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(_DEBOUNCE_MS)
        self._save_timer.timeout.connect(self._emit_save)

        theme_manager().bind_stylesheet(self)

    def is_dirty(self) -> bool:
        return self._dirty

    def current_body(self) -> str:
        return self._editor.toPlainText()

    def selected_text(self) -> str:
        return self._editor.textCursor().selectedText().replace("\u2029", "\n")

    def replace_memo_body(self, body: str) -> None:
        self._loading = True
        self._editor.setPlainText(body)
        self._loading = False
        self._on_text_changed()

    def set_ai_busy(self, busy: bool) -> None:
        self._ai_button.setEnabled(not busy)
        self._editor.setEnabled(not busy)
        if busy:
            self._ai_button.setText("扩写中…")
            self._status_label.setText("AI 处理中…")
        else:
            self._ai_button.setText("AI 扩写")

    def load_body(self, body: str) -> None:
        text = body or ""
        self._loading = True
        self._editor.setPlainText(text)
        self._last_saved_body = text
        self._dirty = False
        self._loading = False
        self._set_status_saved()

    def clear(self) -> None:
        self.load_body("")

    def focus_editor(self) -> None:
        self._editor.setFocus(QtCore.Qt.FocusReason.OtherFocusReason)

    def flush_if_dirty(self) -> None:
        self._save_timer.stop()
        if self._dirty:
            self._emit_save()

    def _on_text_changed(self) -> None:
        if self._loading:
            return
        current = self._editor.toPlainText()
        self._dirty = current != self._last_saved_body
        if self._dirty:
            self._status_label.setText("编辑中…")
            self._save_timer.start()
        else:
            self._set_status_saved()

    def _emit_save(self) -> None:
        if not self._dirty:
            return
        self._dirty = False
        self._last_saved_body = self._editor.toPlainText()
        self._status_label.setText("保存中…")
        self.memo_changed.emit()

    def mark_saved(self, *, failed: bool = False) -> None:
        if failed:
            self._dirty = True
            self._status_label.setText("保存失败")
            return
        self._last_saved_body = self._editor.toPlainText()
        self._dirty = False
        self._set_status_saved()

    def _set_status_saved(self) -> None:
        now = QtCore.QDateTime.currentDateTime().toString("HH:mm:ss")
        self._status_label.setText(f"已保存 {now}")
