"""备忘 Tab：Markdown 编辑与预览。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.ui.markdown_render import render_markdown_html
from vnpy_common.ui.theme import theme_manager

_DEBOUNCE_MS = 800


class NotesCenterMemoView(QtWidgets.QWidget):
    memo_changed = QtCore.Signal()
    ai_expand_requested = QtCore.Signal()

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("NotesCenterMemoView")
        self._dirty = False
        self._loading = False
        self._last_saved_body = ""
        self._preview_mode = False

        self._editor = QtWidgets.QPlainTextEdit(self)
        self._editor.setObjectName("NotesCenterMemoEditor")
        self._editor.setPlaceholderText("研究逻辑、估值区间、AI 分析摘要…（Markdown）")
        self._editor.textChanged.connect(self._on_text_changed)

        self._preview = QtWidgets.QTextBrowser(self)
        self._preview.setObjectName("NotesCenterMemoPreview")
        self._preview.setOpenExternalLinks(True)

        self._stack = QtWidgets.QStackedWidget(self)
        self._stack.addWidget(self._editor)
        self._stack.addWidget(self._preview)

        toolbar = QtWidgets.QHBoxLayout()
        self._ai_button = QtWidgets.QPushButton("AI 扩写", self)
        self._ai_button.setObjectName("SecondaryButton")
        self._ai_button.setToolTip("扩写选中段落；未选中时扩写全文")
        self._ai_button.clicked.connect(self.ai_expand_requested.emit)
        self._toggle_button = QtWidgets.QPushButton("预览", self)
        self._toggle_button.setObjectName("SecondaryButton")
        self._toggle_button.clicked.connect(self._toggle_preview)

        self._status_label = QtWidgets.QLabel("", self)
        self._status_label.setObjectName("StockNoteStatus")

        toolbar.addWidget(self._ai_button)
        toolbar.addWidget(self._toggle_button)
        toolbar.addStretch()
        toolbar.addWidget(self._status_label)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addLayout(toolbar)
        layout.addWidget(self._stack, stretch=1)

        self._save_timer = QtCore.QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(_DEBOUNCE_MS)
        self._save_timer.timeout.connect(self._emit_save)

        theme_manager().bind_stylesheet(self)
        theme_manager().register_callback(self._refresh_preview_if_needed)

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
        self._toggle_button.setEnabled(not busy)
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
        self._refresh_preview()
        self._set_status_saved()

    def clear(self) -> None:
        self.load_body("")

    def flush_if_dirty(self) -> None:
        self._save_timer.stop()
        if self._dirty:
            self._emit_save()

    def mark_saved(self, *, failed: bool = False) -> None:
        if failed:
            self._dirty = True
            self._status_label.setText("保存失败")
            return
        self._last_saved_body = self._editor.toPlainText()
        self._dirty = False
        self._set_status_saved()

    def _toggle_preview(self) -> None:
        if self._preview_mode:
            self._preview_mode = False
            self._stack.setCurrentWidget(self._editor)
            self._toggle_button.setText("预览")
            return
        self._preview_mode = True
        self._refresh_preview()
        self._stack.setCurrentWidget(self._preview)
        self._toggle_button.setText("编辑")

    def _refresh_preview(self) -> None:
        self._preview.setHtml(render_markdown_html(self._editor.toPlainText()))

    def _refresh_preview_if_needed(self) -> None:
        if self._preview_mode:
            self._refresh_preview()

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

    def _set_status_saved(self) -> None:
        now = QtCore.QDateTime.currentDateTime().toString("HH:mm:ss")
        self._status_label.setText(f"已保存 {now}")
