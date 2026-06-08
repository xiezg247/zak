"""AI 对话面板（Dock / 全屏共用）。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtGui, QtWidgets

from vnpy_ashare.ui.qt_helpers import release_thread, retain_thread_until_finished

from vnpy_llm.engine import LlmEngine
from vnpy_llm.tools_status import ToolsStatusSnapshot
from vnpy_llm.ui.styles import PANEL_STYLESHEET
from vnpy_llm.ui.tools_widgets import AiToolsDialog, AiToolsStatusBar
from vnpy_llm.ui.session_widgets import show_ai_session_dialog
from vnpy_ashare.ai.context import QuickAction
from vnpy_llm.ui.floating_widgets import QuickActionChips
from vnpy_llm.ui.md_renderer import render_markdown
from vnpy_llm.ui.worker import ChatWorker

# 股票代码正则：6位数字
import re
_STOCK_CODE_RE = re.compile(r"\b(\d{6})\b")


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
        self._streaming_bubble: QtWidgets.QWidget | None = None
        self._context_text = ""
        self._tool_hint: QtWidgets.QLabel | None = None
        self._skip_completion_once = False

        self.setObjectName("AiChatPanel")
        if self.floating:
            self.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)
        else:
            self.setStyleSheet(PANEL_STYLESHEET)
        self._build_ui()
        self._connect_signals()
        self.scroll.viewport().installEventFilter(self)
        self._refresh_messages()
        self._update_model_action()

    def _build_ui(self) -> None:
        root = QtWidgets.QVBoxLayout(self)
        if self.floating:
            root.setContentsMargins(8, 4, 8, 8)
            root.setSpacing(6)
        else:
            root.setContentsMargins(8 if self.compact else 12, 6, 8 if self.compact else 12, 6)
            root.setSpacing(6)

        if not self.floating:
            self._build_header(root)

        self.tools_status_bar = AiToolsStatusBar(self)
        self.tools_status_bar.open_details_requested.connect(self._on_show_tools)
        if self.floating:
            self.tools_status_bar.hide()
            self._tool_hint = QtWidgets.QLabel()
            self._tool_hint.setObjectName("AiFloatingToolHint")
            self._tool_hint.setWordWrap(True)
            self._tool_hint.hide()
            root.addWidget(self._tool_hint)
        else:
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
        if not self.floating:
            root.addWidget(self.context_label)

        self.scroll = QtWidgets.QScrollArea()
        self.scroll.setObjectName("AiMessageScroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        if self.floating:
            self.scroll.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)
            self.scroll.viewport().setAttribute(
                QtCore.Qt.WidgetAttribute.WA_StyledBackground, True
            )

        self.message_container = QtWidgets.QWidget()
        self.message_container.setObjectName("AiMessageContainer")
        if self.floating:
            self.message_container.setAttribute(
                QtCore.Qt.WidgetAttribute.WA_StyledBackground, True
            )
        self.message_layout = QtWidgets.QVBoxLayout(self.message_container)
        self.message_layout.setContentsMargins(0, 0, 0, 0)
        self.message_layout.setSpacing(6)
        self.message_layout.addStretch()
        self.scroll.setWidget(self.message_container)
        if self.floating:
            self.scroll.setMinimumHeight(100)
        root.addWidget(self.scroll, stretch=1)
        QtCore.QTimer.singleShot(0, self._on_panel_shown)

        # ── 快捷指令面板（浮动/桌面紧凑模式） ──
        self.quick_actions: QuickActionChips | None = None
        if self.floating or self.compact:
            self.quick_actions = QuickActionChips(self)
            self.quick_actions.triggered.connect(self._on_quick_action)
            root.addWidget(self.quick_actions)

        # ── 代码补全弹窗 ──
        self._completion_popup = QtWidgets.QListWidget()
        self._completion_popup.setObjectName("AiCompletionPopup")
        self._completion_popup.setWindowFlags(
            QtCore.Qt.WindowType.Popup | QtCore.Qt.WindowType.FramelessWindowHint
        )
        self._completion_popup.setMaximumHeight(240)
        self._completion_popup.setHorizontalScrollBarPolicy(
            QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._completion_popup.itemClicked.connect(self._on_completion_selected)
        self._completion_popup.itemActivated.connect(self._on_completion_selected)
        self._completion_popup.hide()

        input_row = QtWidgets.QHBoxLayout()
        input_row.setSpacing(6)
        input_row.setAlignment(QtCore.Qt.AlignmentFlag.AlignBottom)
        self.input_box = QtWidgets.QPlainTextEdit()
        self.input_box.setObjectName("AiInput")
        self.input_box.setPlaceholderText(
            "问点什么…" if self.floating else "输入问题，Ctrl+Enter 发送…"
        )
        line_height = self.input_box.fontMetrics().lineSpacing()
        if self.floating:
            self._input_min_height = max(44, line_height + 20)
            self._input_max_height = line_height * 5 + 24
        else:
            min_lines = 2 if self.compact else 2
            max_lines = 5 if self.compact else 5
            self._input_min_height = line_height * min_lines + 16
            self._input_max_height = line_height * max_lines + 16
        self.input_box.document().setDocumentMargin(4 if self.floating else 2)
        self.input_box.setVerticalScrollBarPolicy(
            QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded if self.floating
            else QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.input_box.setMinimumHeight(self._input_min_height)
        self.input_box.setMaximumHeight(self._input_max_height)
        self.input_box.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Minimum,
        )
        self.input_box.setFixedHeight(self._input_min_height)
        self.input_box.document().documentLayout().documentSizeChanged.connect(
            self._on_input_document_changed
        )
        self.input_box.textChanged.connect(self._on_input_text_changed)
        # 方向键在不显示补全时正常导航
        self.input_box.installEventFilter(self)
        input_row.addWidget(self.input_box, stretch=1)

        self.send_btn = QtWidgets.QPushButton("↑" if self.floating else "发送")
        self.send_btn.setObjectName("AiSendBtn")
        if self.floating:
            send_size = max(44, self._input_min_height)
            self.send_btn.setFixedSize(send_size, send_size)
        self.send_btn.clicked.connect(self._on_send)
        input_row.addWidget(self.send_btn)

        input_host = QtWidgets.QWidget()
        input_host.setObjectName("AiInputRow")
        input_host.setLayout(input_row)
        if self.floating:
            input_host.setMinimumHeight(self._input_min_height + 4)
        root.addWidget(input_host, stretch=0)

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

    def _on_input_document_changed(self) -> None:
        doc = self.input_box.document()
        content_height = int(doc.documentLayout().documentSize().height())
        extra = 12 if self.floating else 6
        ideal = max(self._input_min_height, min(content_height + extra, self._input_max_height))
        current = self.input_box.height()
        if abs(ideal - current) > 2:
            self.input_box.setFixedHeight(ideal)
        if not self.floating:
            self.input_box.verticalScrollBar().setVisible(
                content_height > self._input_max_height
            )

    def set_input_text(self, text: str) -> None:
        self._completion_popup.hide()
        self._skip_completion_once = True
        self.input_box.setEnabled(True)
        self.input_box.setPlainText(text.strip())
        self._on_input_document_changed()
        cursor = self.input_box.textCursor()
        cursor.movePosition(QtGui.QTextCursor.MoveOperation.End)
        self.input_box.setTextCursor(cursor)
        self.focus_input()

    def submit_prompt(self, text: str, *, auto_send: bool = False) -> None:
        self.set_input_text(text)
        if auto_send:
            self._on_send()

    def set_quick_actions(self, actions: list[QuickAction]) -> None:
        if self.quick_actions is None:
            return
        self.quick_actions.set_actions(actions)

    # ── 快捷指令 ──
    def _on_quick_action(self, action: QuickAction) -> None:
        """快捷指令：悬浮模式仅回填输入框，不自动发送。"""
        if self.floating:
            self.set_input_text(action.prompt)
            return
        auto_send = action.auto_send or True
        self.submit_prompt(action.prompt, auto_send=auto_send)

    # ── 代码补全 ──
    def _on_input_text_changed(self) -> None:
        """输入框文本变化时，检测股票代码并弹出补全建议。"""
        if self._skip_completion_once:
            self._skip_completion_once = False
            return
        text = self.input_box.toPlainText()
        # 检测最后匹配的股票代码
        codes = _STOCK_CODE_RE.findall(text)
        if not codes:
            self._completion_popup.hide()
            return
        # 取最后一个代码
        code = codes[-1]
        # 展示补全建议
        self._show_completions(code)

    def _show_completions(self, code: str) -> None:
        """在输入框下方弹出操作联想。"""
        from vnpy_ashare.ai.context import build_stock_completion_items
        from vnpy_ashare.ai.session_context import get_ai_context

        ctx = get_ai_context()
        exchange_cn = ctx.exchange if ctx.symbol == code else ""
        stock_name = ctx.name if ctx.symbol == code else ""

        self._completion_popup.clear()
        for entry in build_stock_completion_items(
            code,
            exchange_cn=exchange_cn,
            name=stock_name,
        ):
            list_item = QtWidgets.QListWidgetItem(entry.label)
            list_item.setData(QtCore.Qt.ItemDataRole.UserRole, entry.prompt)
            self._completion_popup.addItem(list_item)

        self._completion_popup.setFixedWidth(
            max(280, self.input_box.width())
        )
        pos = self.input_box.mapToGlobal(
            QtCore.QPoint(0, self.input_box.height())
        )
        self._completion_popup.move(pos)
        self._completion_popup.show()

    def _on_completion_selected(self, item: QtWidgets.QListWidgetItem) -> None:
        """选择了补全项，填入完整 prompt。"""
        prompt = item.data(QtCore.Qt.ItemDataRole.UserRole)
        if not prompt:
            prompt = item.text()
        self.set_input_text(str(prompt))
        self._completion_popup.hide()

    def on_floating_shown(self) -> None:
        """悬浮面板显示后刷新消息区布局。"""
        if not self.floating:
            return
        self._set_busy(False)
        self.input_box.setEnabled(True)
        self._refresh_quick_actions_from_context()
        self.message_container.adjustSize()
        self._refresh_messages()
        QtCore.QTimer.singleShot(100, self._sync_all_bubble_widths)
        QtCore.QTimer.singleShot(300, self._sync_all_bubble_widths)

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
        if self.floating:
            self._refresh_quick_actions_from_context()
            return
        if self._context_text:
            self.context_label.setText(self._context_text)
            self.context_label.setVisible(True)
        else:
            self.context_label.setVisible(False)
        self._refresh_quick_actions()

    def _refresh_quick_actions_from_context(self) -> None:
        """悬浮模式：上下文变化时同步快捷指令。"""
        if self.quick_actions is None:
            return
        from vnpy_ashare.ai.session_context import get_ai_context
        from vnpy_llm.ui.floating_actions import _build_actions

        ctx = get_ai_context()
        self.quick_actions.set_actions(_build_actions(ctx))

    def _refresh_quick_actions(self) -> None:
        """根据当前 AI 上下文刷新快捷指令按钮。"""
        if self.quick_actions is None or self.floating:
            return
        from vnpy_ashare.ai.session_context import get_ai_context
        from vnpy_llm.ui.floating_actions import _build_actions
        ctx = get_ai_context()
        actions = _build_actions(ctx)
        self.quick_actions.set_actions(actions)

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
            if msg.role not in ("user", "assistant", "error"):
                continue
            if msg.role == "assistant" and not msg.content.strip():
                continue
            if msg.role == "assistant":
                self._insert_assistant_html_bubble(msg.content)
            else:
                self._append_bubble(msg.role, msg.content, persist=False)
        self._sync_all_bubble_widths()
        self._scroll_to_bottom()

    def _message_viewport_width(self) -> int:
        viewport_width = self.scroll.viewport().width()
        if viewport_width >= 100:
            return viewport_width
        fallback = self.scroll.width()
        if fallback >= 100:
            return fallback
        margin = 16 if (not self.compact and not self.floating) else 8
        return max(200, self.width() - margin * 2)

    def _usable_message_width(self) -> int:
        viewport_width = self._message_viewport_width()
        margin = 8 if self.floating else 4
        return max(200, viewport_width - margin * 2)

    def _bubble_max_width(self, role: str) -> int:
        usable = self._usable_message_width()
        if role == "user":
            return int(usable * 0.72)
        if self.floating:
            return int(usable * 0.94)
        if self.compact:
            return int(usable * 0.88)
        return int(usable * 0.82)

    @staticmethod
    def _bubble_horizontal_padding() -> int:
        return 28

    def _user_label_width(self, bubble: QtWidgets.QLabel, max_width: int) -> int:
        text = bubble.text()
        padding = self._bubble_horizontal_padding()
        if not text.strip():
            return min(max_width, 120)
        metrics = bubble.fontMetrics()
        single_line = metrics.horizontalAdvance(text) + padding
        if single_line <= max_width:
            return max(64, single_line)
        return max_width

    @staticmethod
    def _apply_widget_width(widget: QtWidgets.QWidget, width: int) -> None:
        widget.setMinimumWidth(width)
        widget.setMaximumWidth(width)

    @staticmethod
    def _bubble_role(widget: QtWidgets.QWidget) -> str:
        name = widget.objectName()
        if name == "AiBubbleUser":
            return "user"
        if name == "AiBubbleError":
            return "error"
        return "assistant"

    def _sync_label_bubble(self, bubble: QtWidgets.QLabel) -> None:
        role = self._bubble_role(bubble)
        max_width = self._bubble_max_width(role)
        if role == "user":
            width = self._user_label_width(bubble, max_width)
        else:
            width = max_width
        self._apply_widget_width(bubble, width)
        wrapped_height = bubble.heightForWidth(width)
        if wrapped_height > 0:
            bubble.setMinimumHeight(wrapped_height)

    def _fit_floating_bubble(self, bubble: QtWidgets.QTextBrowser) -> None:
        """已不再使用 QTextBrowser；保留以防残留。"""

    def _sync_all_bubble_widths(self) -> None:
        for bubble in self._iter_message_bubbles():
            if isinstance(bubble, QtWidgets.QLabel):
                self._sync_label_bubble(bubble)
            elif isinstance(bubble, QtWidgets.QTextBrowser):
                self._sync_browser_bubble(bubble)

    def _sync_browser_bubble(self, browser: QtWidgets.QTextBrowser) -> None:
        role = self._bubble_role(browser)
        width = self._bubble_max_width(role)
        content_width = max(120, width - self._bubble_horizontal_padding())
        self._apply_widget_width(browser, width)
        browser.document().setTextWidth(content_width)
        doc_height = int(browser.document().size().height())
        if doc_height > 0:
            browser.setMinimumHeight(doc_height + 20)
            browser.setFixedHeight(doc_height + 20)

    def _iter_message_bubbles(self):
        for index in range(self.message_layout.count() - 1):
            row = self.message_layout.itemAt(index).widget()
            if row is None:
                continue
            for child in row.findChildren(QtWidgets.QLabel):
                if child.objectName().startswith("AiBubble"):
                    yield child
            for child in row.findChildren(QtWidgets.QTextBrowser):
                if child.objectName().startswith("AiBubble"):
                    yield child

    def _create_label_bubble(self, role: str, content: str) -> QtWidgets.QLabel:
        bubble = QtWidgets.QLabel(content)
        bubble.setWordWrap(True)
        bubble.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
        bubble.setMinimumWidth(40)
        bubble.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Preferred,
            QtWidgets.QSizePolicy.Policy.Preferred,
        )
        if role == "user":
            bubble.setObjectName("AiBubbleUser")
            bubble.setAlignment(
                QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignTop
            )
        elif role == "error":
            bubble.setObjectName("AiBubbleError")
            bubble.setAlignment(
                QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignTop
            )
        else:
            bubble.setObjectName("AiBubbleAssistant")
            bubble.setAlignment(
                QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignTop
            )
        return bubble

    def _insert_bubble_row(self, role: str, bubble: QtWidgets.QWidget) -> None:
        row = QtWidgets.QWidget()
        row.setObjectName("AiBubbleRow")
        if self.floating:
            row.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)
        row_layout = QtWidgets.QHBoxLayout(row)
        row_layout.setContentsMargins(2, 2, 2, 2)
        row_layout.setSpacing(0)
        if role == "user":
            row_layout.addStretch(1)
            row_layout.addWidget(bubble, 0, QtCore.Qt.AlignmentFlag.AlignRight)
        else:
            row_layout.addWidget(bubble, 0, QtCore.Qt.AlignmentFlag.AlignLeft)
            row_layout.addStretch(1)
        insert_at = max(0, self.message_layout.count() - 1)
        self.message_layout.insertWidget(insert_at, row)

    def _insert_assistant_html_bubble(self, content: str) -> None:
        """插入一条助手消息气泡，以 HTML 方式渲染 Markdown。"""
        html = render_markdown(content)
        browser = QtWidgets.QTextBrowser()
        browser.setObjectName("AiBubbleAssistant")
        browser.setOpenExternalLinks(True)
        browser.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        browser.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        browser.setMinimumWidth(40)
        browser.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Preferred,
            QtWidgets.QSizePolicy.Policy.Preferred,
        )
        browser.setHtml(html)
        self._sync_browser_bubble(browser)
        self._insert_bubble_row("assistant", browser)

    def _append_bubble(self, role: str, content: str, *, persist: bool) -> QtWidgets.QWidget:
        bubble = self._create_label_bubble(role, content)
        self._insert_bubble_row(role, bubble)
        self._sync_label_bubble(bubble)
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
        self.input_box.setFixedHeight(self._input_min_height)
        self._set_busy(True)
        self._append_bubble("user", text, persist=True)
        worker = ChatWorker(self.engine, text, None)
        self._worker = worker
        retain_thread_until_finished(self._retired_workers, worker)
        worker.finished_ok.connect(self._on_worker_done)
        worker.failed.connect(self._on_worker_failed)
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def _set_busy(self, busy: bool) -> None:
        self.send_btn.setDisabled(busy)
        self.input_box.setDisabled(busy)

    def _on_stream_started(self) -> None:
        self._streaming_bubble = self._append_bubble("assistant", "", persist=True)

    def _append_stream_delta(self, delta: str) -> None:
        if self._streaming_bubble is None:
            return
        widget = self._streaming_bubble
        if isinstance(widget, QtWidgets.QLabel):
            widget.setText(widget.text() + delta)
            self._sync_label_bubble(widget)
        elif isinstance(widget, QtWidgets.QTextBrowser):
            widget.setPlainText(widget.toPlainText() + delta)
            self._fit_floating_bubble(widget)

    def _on_stream_delta(self, delta: str) -> None:
        self._append_stream_delta(delta)
        self._scroll_to_bottom()

    def _on_stream_finished(self) -> None:
        if self._streaming_bubble is not None:
            self._sync_all_bubble_widths()
        self._streaming_bubble = None

    def _remove_streaming_bubble(self) -> None:
        if self._streaming_bubble is None:
            return
        row = self._streaming_bubble.parentWidget()
        if row is not None:
            row.deleteLater()
        else:
            self._streaming_bubble.deleteLater()
        self._streaming_bubble = None

    def _on_stream_failed(self, message: str) -> None:
        self._remove_streaming_bubble()
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
        if self.floating and self._tool_hint is not None:
            self._tool_hint.setText(f"⏳ 正在 {display}…")
            self._tool_hint.show()
        else:
            self.tools_status_bar.show_progress(f"正在 {display}…")

    def _on_tool_call_finished(self, name: str) -> None:
        if self.floating and self._tool_hint is not None:
            self._tool_hint.hide()
        else:
            self.tools_status_bar.hide_progress()

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

    def eventFilter(self, obj: QtCore.QObject, event: QtCore.QEvent) -> bool:
        if (
            obj is self.scroll.viewport()
            and event.type() == QtCore.QEvent.Type.Resize
        ):
            self.message_container.setMinimumWidth(self._message_viewport_width())
            self._sync_all_bubble_widths()
        if obj is self.input_box and event.type() == QtCore.QEvent.Type.KeyPress:
            key_event = event
            if self._completion_popup.isVisible():
                if key_event.key() == QtCore.Qt.Key.Key_Down:
                    self._completion_popup.setFocus()
                    self._completion_popup.setCurrentRow(0)
                    return True
                if key_event.key() == QtCore.Qt.Key.Key_Escape:
                    self._completion_popup.hide()
                    return True
                if key_event.key() in (
                    QtCore.Qt.Key.Key_Return,
                    QtCore.Qt.Key.Key_Enter,
                ):
                    if key_event.modifiers() & QtCore.Qt.KeyboardModifier.ControlModifier:
                        self._completion_popup.hide()
                        return False
                    self._completion_popup.hide()
                    return False
        return super().eventFilter(obj, event)

    def showEvent(self, event: QtGui.QShowEvent) -> None:
        super().showEvent(event)
        QtCore.QTimer.singleShot(0, self._on_panel_shown)

    def _on_panel_shown(self) -> None:
        self.message_container.setMinimumWidth(self._message_viewport_width())
        self._sync_all_bubble_widths()

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        if (
            event.key() in (QtCore.Qt.Key.Key_Return, QtCore.Qt.Key.Key_Enter)
            and event.modifiers() & QtCore.Qt.KeyboardModifier.ControlModifier
        ):
            self._on_send()
            event.accept()
            return
        super().keyPressEvent(event)

    def _disconnect_engine_signals(self) -> None:
        signals = self.engine.signals
        for signal, slot in (
            (signals.messages_changed, self._refresh_messages),
            (signals.stream_started, self._on_stream_started),
            (signals.stream_delta, self._on_stream_delta),
            (signals.stream_finished, self._on_stream_finished),
            (signals.stream_failed, self._on_stream_failed),
            (signals.context_changed, self._on_context_changed),
            (signals.tools_status_changed, self._on_tools_status_changed),
            (signals.tool_call_started, self._on_tool_call_started),
            (signals.tool_call_finished, self._on_tool_call_finished),
        ):
            try:
                signal.disconnect(slot)
            except (RuntimeError, TypeError):
                pass

    def deactivate(self, *, final: bool = False) -> None:
        self._set_busy(False)
        self._completion_popup.hide()
        if final:
            self._disconnect_engine_signals()
        worker = self._worker
        self._worker = None
        if final and worker is not None:
            worker.safe_stop()
        else:
            release_thread(self._retired_workers, worker, timeout_ms=5000)
        if final:
            for retired in list(self._retired_workers):
                if isinstance(retired, ChatWorker):
                    retired.safe_stop()
                else:
                    release_thread(self._retired_workers, retired, timeout_ms=2000)
