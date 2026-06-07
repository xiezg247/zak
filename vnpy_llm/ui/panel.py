"""AI 对话面板（Dock / 全屏共用）。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtGui, QtWidgets

from vnpy_llm.engine import LlmEngine
from vnpy_llm.ui.styles import PANEL_STYLESHEET
from vnpy_llm.ui.worker import ChatWorker


class AiChatPanel(QtWidgets.QWidget):
    expand_requested = QtCore.Signal()
    collapse_requested = QtCore.Signal()

    def __init__(
        self,
        engine: LlmEngine,
        *,
        compact: bool = False,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.engine = engine
        self.compact = compact
        self._worker: ChatWorker | None = None
        self._streaming_bubble: QtWidgets.QLabel | None = None
        self._context_text = ""

        self.setObjectName("AiChatPanel")
        self.setStyleSheet(PANEL_STYLESHEET)
        self._build_ui()
        self._connect_signals()
        self._refresh_messages()
        self._update_model_action()

    def _build_ui(self) -> None:
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(8 if self.compact else 16, 8, 8 if self.compact else 16, 8)
        root.setSpacing(8)

        header = QtWidgets.QHBoxLayout()

        if self.compact:
            title = QtWidgets.QLabel("AI 助手")
            title.setObjectName("AiTitle")
            header.addWidget(title)
            header.addStretch()
            expand_btn = QtWidgets.QPushButton("全屏")
            expand_btn.setObjectName("AiToolBtn")
            expand_btn.clicked.connect(self.expand_requested.emit)
            header.addWidget(expand_btn)
        else:
            back_btn = QtWidgets.QPushButton("← 返回看盘")
            back_btn.setObjectName("AiToolBtn")
            back_btn.clicked.connect(self.collapse_requested.emit)
            header.addWidget(back_btn)
            header.addStretch()

        more_btn = QtWidgets.QPushButton("···")
        more_btn.setObjectName("AiToolBtn")
        more_btn.setFixedWidth(36)
        more_menu = QtWidgets.QMenu(more_btn)
        more_menu.addAction("新会话", self._on_new_session)
        more_menu.addAction("清空会话", self._on_clear)
        more_menu.addSeparator()
        self._model_action = more_menu.addAction("")
        self._model_action.setEnabled(False)
        more_btn.clicked.connect(
            lambda: more_menu.exec(more_btn.mapToGlobal(more_btn.rect().bottomLeft()))
        )
        header.addWidget(more_btn)

        root.addLayout(header)

        if self.compact:
            shortcut_hint = QtWidgets.QLabel("Ctrl+L / ⌘L 开关侧栏 · 全屏进入专注模式")
            shortcut_hint.setObjectName("AiConfigHint")
            shortcut_hint.setWordWrap(True)
            root.addWidget(shortcut_hint)

        self.context_label = QtWidgets.QLabel()
        self.context_label.setObjectName("AiContextLabel")
        self.context_label.setWordWrap(True)
        self.context_label.setVisible(False)
        root.addWidget(self.context_label)

        self.scroll = QtWidgets.QScrollArea()
        self.scroll.setObjectName("AiMessageScroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.message_container = QtWidgets.QWidget()
        self.message_container.setObjectName("AiMessageContainer")
        self.message_layout = QtWidgets.QVBoxLayout(self.message_container)
        self.message_layout.setContentsMargins(0, 0, 0, 0)
        self.message_layout.setSpacing(8)
        self.message_layout.addStretch()
        self.scroll.setWidget(self.message_container)
        root.addWidget(self.scroll, stretch=1)

        input_row = QtWidgets.QHBoxLayout()
        self.input_box = QtWidgets.QPlainTextEdit()
        self.input_box.setObjectName("AiInput")
        self.input_box.setPlaceholderText("输入问题，Ctrl+Enter 发送…")
        line_height = self.input_box.fontMetrics().lineSpacing()
        self.input_box.setFixedHeight(line_height * 3 + 16)
        input_row.addWidget(self.input_box, stretch=1)

        self.send_btn = QtWidgets.QPushButton("发送")
        self.send_btn.setObjectName("AiSendBtn")
        self.send_btn.clicked.connect(self._on_send)
        input_row.addWidget(self.send_btn)
        root.addLayout(input_row)

    def _connect_signals(self) -> None:
        signals = self.engine.signals
        signals.messages_changed.connect(self._refresh_messages)
        signals.stream_started.connect(self._on_stream_started)
        signals.stream_delta.connect(self._on_stream_delta)
        signals.stream_finished.connect(self._on_stream_finished)
        signals.stream_failed.connect(self._on_stream_failed)
        signals.context_changed.connect(self._on_context_changed)

    def focus_input(self) -> None:
        self.input_box.setFocus(QtCore.Qt.FocusReason.ShortcutFocusReason)

    def _update_model_action(self) -> None:
        cfg = self.engine.config
        if cfg.configured:
            self._model_action.setText(f"模型：{cfg.model}")
        else:
            self._model_action.setText("未配置 LLM_API_KEY（.env）")

    def _on_context_changed(self, text: str) -> None:
        self._context_text = text.strip()
        if self._context_text:
            self.context_label.setText(self._context_text)
            self.context_label.setVisible(True)
        else:
            self.context_label.setVisible(False)

    def _clear_message_widgets(self) -> None:
        while self.message_layout.count() > 1:
            item = self.message_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._streaming_bubble = None

    def _refresh_messages(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            return
        self._clear_message_widgets()
        for msg in self.engine.get_messages():
            self._append_bubble(msg.role, msg.content, persist=False)
        self._scroll_to_bottom()

    def _append_bubble(self, role: str, content: str, *, persist: bool) -> QtWidgets.QLabel:
        bubble = QtWidgets.QLabel(content)
        bubble.setWordWrap(True)
        bubble.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
        if role == "user":
            bubble.setObjectName("AiBubbleUser")
            bubble.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignTop)
        elif role == "error":
            bubble.setObjectName("AiBubbleError")
        else:
            bubble.setObjectName("AiBubbleAssistant")
        insert_at = max(0, self.message_layout.count() - 1)
        self.message_layout.insertWidget(insert_at, bubble)
        if persist:
            self._scroll_to_bottom()
        return bubble

    def _scroll_to_bottom(self) -> None:
        QtCore.QTimer.singleShot(0, lambda: self.scroll.verticalScrollBar().setValue(
            self.scroll.verticalScrollBar().maximum()
        ))

    def _on_send(self) -> None:
        text = self.input_box.toPlainText().strip()
        if not text:
            return
        if self._worker is not None and self._worker.isRunning():
            return
        if not self.engine.config.configured:
            QtWidgets.QMessageBox.warning(self, "提示", "请先在 .env 中配置 LLM_API_KEY")
            return

        self.input_box.clear()
        self._set_busy(True)
        worker = ChatWorker(self.engine, text, self)
        self._worker = worker
        worker.finished_ok.connect(self._on_worker_done)
        worker.failed.connect(self._on_worker_failed)
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def _set_busy(self, busy: bool) -> None:
        self.send_btn.setDisabled(busy)
        self.input_box.setDisabled(busy)

    def _on_stream_started(self) -> None:
        self._streaming_bubble = self._append_bubble("assistant", "", persist=True)

    def _on_stream_delta(self, delta: str) -> None:
        if self._streaming_bubble is None:
            return
        self._streaming_bubble.setText(self._streaming_bubble.text() + delta)
        self._scroll_to_bottom()

    def _on_stream_finished(self) -> None:
        self._streaming_bubble = None

    def _on_stream_failed(self, message: str) -> None:
        if self._streaming_bubble is not None:
            self._streaming_bubble.deleteLater()
            self._streaming_bubble = None
        self._append_bubble("error", f"生成失败：{message}", persist=True)

    def _on_worker_done(self) -> None:
        self._worker = None
        self._set_busy(False)
        self._refresh_messages()

    def _on_worker_failed(self, message: str) -> None:
        self._worker = None
        self._set_busy(False)
        if message:
            self._append_bubble("error", message, persist=True)

    def _on_clear(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            return
        reply = QtWidgets.QMessageBox.question(
            self, "确认", "清空当前会话的所有消息？",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
        )
        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            self.engine.clear_session()

    def _on_new_session(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            return
        self.engine.new_session()

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        if (
            event.key() in (QtCore.Qt.Key.Key_Return, QtCore.Qt.Key.Key_Enter)
            and event.modifiers() & QtCore.Qt.KeyboardModifier.ControlModifier
        ):
            self._on_send()
            event.accept()
            return
        super().keyPressEvent(event)

    def deactivate(self) -> None:
        worker = self._worker
        if worker is not None and worker.isRunning():
            worker.wait(500)
