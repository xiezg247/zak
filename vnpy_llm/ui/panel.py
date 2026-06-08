"""AI 对话面板（Dock / 全屏共用）。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtGui, QtWidgets

from vnpy_ashare.ui.qt_helpers import release_thread

from vnpy_llm.engine import LlmEngine
from vnpy_llm.tools_status import ToolsStatusSnapshot
from vnpy_llm.ui.styles import PANEL_STYLESHEET
from vnpy_llm.ui.tools_widgets import AiToolsDialog, AiToolsStatusBar
from vnpy_llm.ui.session_widgets import show_ai_session_dialog
from vnpy_llm.ui.worker import ChatWorker


class AiChatPanel(QtWidgets.QWidget):
    expand_requested = QtCore.Signal()
    collapse_requested = QtCore.Signal()

    def __init__(
        self,
        engine: LlmEngine,
        *,
        compact: bool = False,
        floating: bool = False,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.engine = engine
        self.compact = compact
        self.floating = floating
        if self.floating:
            self.setProperty("floating", True)
        self._worker: ChatWorker | None = None
        self._retired_workers: list[QtCore.QThread] = []
        self._streaming_bubble: QtWidgets.QLabel | None = None
        self._context_text = ""

        self.setObjectName("AiChatPanel")
        if not self.floating:
            self.setStyleSheet(PANEL_STYLESHEET)
        self._build_ui()
        self._connect_signals()
        self._refresh_messages()
        self._update_model_action()

    def _build_ui(self) -> None:
        root = QtWidgets.QVBoxLayout(self)
        if self.floating:
            root.setContentsMargins(8, 4, 8, 8)
            root.setSpacing(6)
        else:
            root.setContentsMargins(8 if self.compact else 16, 8, 8 if self.compact else 16, 8)
            root.setSpacing(8)

        if not self.floating:
            self._build_header(root)

        self.tools_status_bar = AiToolsStatusBar(self)
        self.tools_status_bar.open_details_requested.connect(self._on_show_tools)
        if self.floating:
            self.tools_status_bar.hide()
        root.addWidget(self.tools_status_bar)

        if self.compact and not self.floating:
            shortcut_hint = QtWidgets.QLabel("Ctrl+L / ⌘L 显示悬浮球 · 全屏进入专注模式")
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
        self.message_layout.setSpacing(6 if self.floating else 8)
        self.message_layout.addStretch()
        self.scroll.setWidget(self.message_container)
        root.addWidget(self.scroll, stretch=1)

        input_row = QtWidgets.QHBoxLayout()
        input_row.setSpacing(6)
        self.input_box = QtWidgets.QPlainTextEdit()
        self.input_box.setObjectName("AiInput")
        self.input_box.setPlaceholderText(
            "问点什么…" if self.floating else "输入问题，Ctrl+Enter 发送…"
        )
        line_height = self.input_box.fontMetrics().lineSpacing()
        input_lines = 2 if self.floating else 3
        self.input_box.setFixedHeight(line_height * input_lines + (10 if self.floating else 16))
        input_row.addWidget(self.input_box, stretch=1)

        self.send_btn = QtWidgets.QPushButton("↑" if self.floating else "发送")
        self.send_btn.setObjectName("AiSendBtn")
        if self.floating:
            self.send_btn.setFixedSize(36, 36)
        self.send_btn.clicked.connect(self._on_send)
        input_row.addWidget(self.send_btn)
        root.addLayout(input_row)

    def _build_header(self, root: QtWidgets.QVBoxLayout) -> None:
        header = QtWidgets.QHBoxLayout()

        if self.compact:
            title = QtWidgets.QLabel("AI 助手")
            title.setObjectName("AiTitle")
            header.addWidget(title)
            header.addStretch()
            history_btn = QtWidgets.QPushButton("历史")
            history_btn.setObjectName("AiToolBtn")
            history_btn.clicked.connect(self._on_show_sessions)
            header.addWidget(history_btn)
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
        more_menu.addAction("AI 工具能力…", self._on_show_tools)
        more_menu.addAction("重新加载工具", self._on_reload_tools)
        more_menu.addSeparator()
        more_menu.addAction("历史会话…", self._on_show_sessions)
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

    def _connect_signals(self) -> None:
        signals = self.engine.signals
        signals.messages_changed.connect(self._refresh_messages)
        signals.stream_started.connect(self._on_stream_started)
        signals.stream_delta.connect(self._on_stream_delta)
        signals.stream_finished.connect(self._on_stream_finished)
        signals.stream_failed.connect(self._on_stream_failed)
        signals.context_changed.connect(self._on_context_changed)
        signals.tools_status_changed.connect(self._on_tools_status_changed)
        signals.tool_call_started.connect(self._on_tool_call_started)
        signals.tool_call_finished.connect(self._on_tool_call_finished)
        self._on_tools_status_changed(self.engine.get_tools_status())

    def focus_input(self) -> None:
        self.input_box.setFocus(QtCore.Qt.FocusReason.ShortcutFocusReason)

    def set_input_text(self, text: str) -> None:
        self.input_box.setPlainText(text.strip())
        self.focus_input()

    def _update_model_action(self) -> None:
        if self.floating:
            return
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

    def _on_tool_call_started(self, name: str) -> None:
        label_map = {
            "get_quote_context": "读取当前上下文",
            "get_watchlist": "查询自选池",
            "get_bars_summary": "查询K线概览",
            "get_bars_data": "加载K线数据",
            "diagnose_stock": "综合诊断",
            "technical_snapshot": "分析技术形态",
            "list_strategy_signals": "查询策略信号",
            "historical_pattern_summary": "统计历史走势",
            "get_screening_context": "读取选股结果",
            "list_strategies": "列出可用策略",
            "get_backtest_result": "读取回测结果",
            "list_backtest_history": "查询回测历史",
            "list_screeners": "列出选股条件",
            "propose_screening": "解析选股条件",
            "screen_by_condition": "执行选股筛选",
            "add_to_watchlist": "加入自选",
            "remove_from_watchlist": "移出自选",
            "read_skill_file": "读取知识文档",
            "run_python": "执行数据分析",
            "list_skill_files": "列出 Skill 文件",
        }
        display = label_map.get(name)
        if display is None and name.startswith("mcp_tdx_"):
            suffix = name.removeprefix("mcp_tdx_")
            if any(key in suffix for key in ("report", "research", "yanbao", "rating")):
                display = "查询通达信研报"
            elif "f10" in suffix:
                display = "查询通达信 F10"
            elif "quote" in suffix or "price" in suffix:
                display = "查询通达信行情"
            elif "kline" in suffix or "bar" in suffix:
                display = "查询通达信 K 线"
            else:
                display = f"通达信 MCP ({suffix})"
        if display is None:
            display = name
        if self.floating:
            self.tools_status_bar.show()
        self.tools_status_bar.show_progress(f"正在 {display}…")

    def _on_tool_call_finished(self, name: str) -> None:
        self.tools_status_bar.hide_progress()
        if self.floating:
            self.tools_status_bar.hide()

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

    def _on_show_sessions(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            QtWidgets.QMessageBox.information(self, "提示", "请等待当前回复完成后再切换会话")
            return
        if self.engine.is_busy():
            QtWidgets.QMessageBox.information(self, "提示", "请等待当前回复完成后再切换会话")
            return
        show_ai_session_dialog(self.engine, self)

    def _on_tools_status_changed(self, snapshot: ToolsStatusSnapshot) -> None:
        self.tools_status_bar.apply_snapshot(snapshot)

    def _on_show_tools(self) -> None:
        dialog = AiToolsDialog(self.engine, self)
        dialog.reload_requested.connect(
            lambda: self._on_tools_status_changed(self.engine.get_tools_status())
        )
        dialog.exec()

    def _on_reload_tools(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            QtWidgets.QMessageBox.information(self, "提示", "请等待当前回复完成后再重新加载")
            return
        self.engine.reload_tools()

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
        self._worker = None
        release_thread(self._retired_workers, worker)
