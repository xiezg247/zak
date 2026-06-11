"""AI 对话面板（Dock / 全屏 / 浮动精简模式共用）。"""

from __future__ import annotations

# 股票代码正则：6位数字
import re

from vnpy.trader.ui import QtCore, QtGui, QtWidgets

from vnpy_common.ai.access import build_quick_actions_for_panel, build_stock_completion_items, get_ai_context
from vnpy_common.ai.protocol import QuickAction
from vnpy_common.ui.feedback import confirm_action, page_notify
from vnpy_common.ui.qt_helpers import release_thread, retain_thread_until_finished
from vnpy_common.ui.theme import theme_manager
from vnpy_llm.app.engine import LlmEngine
from vnpy_llm.tools.labels import tool_display_name
from vnpy_llm.tools.status import ToolsStatusSnapshot
from vnpy_llm.trace.trace import TurnTrace, map_turns_to_user_messages
from vnpy_llm.ui.dialogs.tools import AiToolsDialog, AiToolsStatusBar
from vnpy_llm.ui.floating.widgets import QuickActionChips
from vnpy_llm.ui.panel.md_renderer import render_markdown
from vnpy_llm.ui.panel.pending_bubble import (
    SPINNER_FRAMES,
    format_pending_html,
    pending_status_from_turn,
)
from vnpy_llm.ui.panel.worker import ChatWorker
from vnpy_llm.ui.session.widgets import show_ai_session_dialog
from vnpy_llm.ui.themed_styles import bind_ai_panel_style
from vnpy_llm.ui.trace.widgets import AiInlineTraceBlock

_STOCK_CODE_RE = re.compile(r"\b(\d{6})\b")


class AiInputEdit(QtWidgets.QPlainTextEdit):
    """输入框：Enter 发送，Ctrl/Cmd+Enter 换行。"""

    enter_pressed = QtCore.Signal(bool)

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        key = event.key()
        if key in (QtCore.Qt.Key.Key_Return, QtCore.Qt.Key.Key_Enter):
            mods = event.modifiers()
            newline = bool(mods & (QtCore.Qt.KeyboardModifier.ControlModifier | QtCore.Qt.KeyboardModifier.MetaModifier))
            self.enter_pressed.emit(newline)
            event.accept()
            return
        super().keyPressEvent(event)


class AiChatPanel(QtWidgets.QWidget):
    """主聊天 UI：消息流、快捷动作、工具状态、内嵌 Trace。

    ``compact``：Dock 窄栏；``floating``：悬浮精简面板（独立 QSS）。
    """

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
        self._live_trace_block: AiInlineTraceBlock | None = None
        self._pending_bubble: QtWidgets.QLabel | None = None
        self._pending_main = "思考中…"
        self._pending_sub = "已收到你的问题"
        self._pending_spinner_index = 0
        self._context_text = ""
        self._tool_hint: QtWidgets.QLabel | None = None
        self._session_label: QtWidgets.QLabel | None = None
        self._skip_completion_once = False
        self._last_action_id = ""
        self._active_tool_name = ""
        self._slow_tool_timer = QtCore.QTimer(self)
        self._slow_tool_timer.setSingleShot(True)
        self._slow_tool_timer.setInterval(3000)
        self._slow_tool_timer.timeout.connect(self._on_tool_call_slow)

        self.setObjectName("AiChatPanel")
        if self.floating:
            self.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)
        else:
            bind_ai_panel_style(self)
        self._build_ui()
        self._pending_timer = QtCore.QTimer(self)
        self._pending_timer.setInterval(400)
        self._pending_timer.timeout.connect(self._tick_pending_spinner)
        self._connect_signals()
        theme_manager().register_callback(self._on_theme_changed)
        self.scroll.viewport().installEventFilter(self)
        self._refresh_messages()
        self._update_model_action()
        self._update_session_hint()

    def _update_session_hint(self) -> None:
        if self._session_label is None:
            return
        title = self.engine.get_current_session_title()
        self._session_label.setText(f"· {title}")
        self._session_label.setToolTip(title)

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
            self.scroll.viewport().setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)

        self.message_container = QtWidgets.QWidget()
        self.message_container.setObjectName("AiMessageContainer")
        if self.floating:
            self.message_container.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)
        self.message_layout = QtWidgets.QVBoxLayout(self.message_container)
        self.message_layout.setContentsMargins(0, 0, 0, 0)
        self.message_layout.setSpacing(6)
        self.message_layout.addStretch()
        self.scroll.setWidget(self.message_container)
        if self.floating:
            self.scroll.setMinimumHeight(100)
        root.addWidget(self.scroll, stretch=1)
        QtCore.QTimer.singleShot(0, self._on_panel_shown)

        # ── 快捷指令面板（输入框上方） ──
        self.quick_actions: QuickActionChips | None = None
        self.quick_actions = QuickActionChips(self)
        self.quick_actions.triggered.connect(self._on_quick_action)
        root.addWidget(self.quick_actions)
        QtCore.QTimer.singleShot(0, self._refresh_quick_actions_from_context)

        # ── 代码补全弹窗 ──
        self._completion_popup = QtWidgets.QListWidget()
        self._completion_popup.setObjectName("AiCompletionPopup")
        self._completion_popup.setWindowFlags(QtCore.Qt.WindowType.Popup | QtCore.Qt.WindowType.FramelessWindowHint)
        self._completion_popup.setMaximumHeight(240)
        self._completion_popup.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._completion_popup.itemClicked.connect(self._on_completion_selected)
        self._completion_popup.itemActivated.connect(self._on_completion_selected)
        self._completion_popup.hide()

        input_row = QtWidgets.QHBoxLayout()
        input_row.setSpacing(6)
        input_row.setAlignment(QtCore.Qt.AlignmentFlag.AlignBottom)
        self.input_box = AiInputEdit()
        self.input_box.setObjectName("AiInput")
        self.input_box.setPlaceholderText("Enter 发送，Ctrl+Enter 换行…")
        self.input_box.enter_pressed.connect(self._on_input_enter)
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
            QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded if self.floating else QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.input_box.setMinimumHeight(self._input_min_height)
        self.input_box.setMaximumHeight(self._input_max_height)
        self.input_box.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Minimum,
        )
        self.input_box.setFixedHeight(self._input_min_height)
        self.input_box.document().documentLayout().documentSizeChanged.connect(self._on_input_document_changed)
        self.input_box.textChanged.connect(self._on_input_text_changed)
        # 方向键在不显示补全时正常导航
        self.input_box.installEventFilter(self)
        self.input_box.viewport().installEventFilter(self)
        input_row.addWidget(self.input_box, stretch=1)

        self.send_btn = QtWidgets.QPushButton("↑" if self.floating else "发送")
        self.send_btn.setObjectName("AiSendBtn")
        if self.floating:
            send_size = max(44, self._input_min_height)
            self.send_btn.setFixedSize(send_size, send_size)
        self.send_btn.clicked.connect(self._on_send_or_stop)
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
            self._session_label = QtWidgets.QLabel("")
            self._session_label.setObjectName("AiSessionChip")
            header.addWidget(self._session_label)
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
            self._session_label = None
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
        more_menu.addAction("重载 LLM 配置", self._on_reload_llm_config)
        more_menu.addSeparator()
        more_menu.addAction("历史会话…", self._on_show_sessions)
        more_menu.addAction("新会话", self._on_new_session)
        more_menu.addAction("清空会话", self._on_clear)
        more_menu.addSeparator()
        self._model_action = more_menu.addAction("")
        self._model_action.setEnabled(False)
        more_btn.clicked.connect(lambda: more_menu.exec(more_btn.mapToGlobal(more_btn.rect().bottomLeft())))
        header.addWidget(more_btn)

        root.addLayout(header)

    def _connect_signals(self) -> None:
        signals = self.engine.signals
        signals.messages_changed.connect(self._refresh_messages)
        signals.stream_started.connect(self._on_stream_started)
        signals.stream_delta.connect(self._on_stream_delta)
        signals.stream_finished.connect(self._on_stream_finished)
        signals.stream_cancelled.connect(self._on_stream_cancelled)
        signals.stream_failed.connect(self._on_stream_failed)
        signals.context_changed.connect(self._on_context_changed)
        signals.tools_status_changed.connect(self._on_tools_status_changed)
        signals.sessions_changed.connect(self._update_session_hint)
        signals.tool_call_started.connect(self._on_tool_call_started)
        signals.tool_call_finished.connect(self._on_tool_call_finished)
        signals.trace_changed.connect(self._on_trace_changed)
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
            self.input_box.verticalScrollBar().setVisible(content_height > self._input_max_height)

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

    def submit_prompt(self, text: str, *, auto_send: bool = False, action_id: str = "") -> None:
        self._last_action_id = action_id.strip()
        self.set_input_text(text)
        if auto_send:
            self._on_send()

    def _panel_mode(self) -> str:
        if self.floating:
            return "floating"
        if self.compact:
            return "compact"
        return "assistant"

    def _refresh_quick_actions_from_context(self) -> None:
        """根据当前 AI 上下文刷新快捷指令按钮。"""
        if self.quick_actions is None:
            return
        ctx = get_ai_context()
        actions = build_quick_actions_for_panel(ctx, mode=self._panel_mode())
        self.quick_actions.set_actions(actions)

    def set_quick_actions(self, actions: list[QuickAction]) -> None:
        if self.quick_actions is None:
            return
        self.quick_actions.set_actions(actions)

    # ── 快捷指令 ──
    def _on_quick_action(self, action: QuickAction) -> None:
        """快捷指令：悬浮/全屏回填输入框；紧凑模式默认直接发送。"""
        if self.floating or self._panel_mode() == "assistant":
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

        self._completion_popup.setFixedWidth(max(280, self.input_box.width()))
        pos = self.input_box.mapToGlobal(QtCore.QPoint(0, self.input_box.height()))
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
        self._refresh_quick_actions_from_context()
        if self.floating:
            return
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
        self._live_trace_block = None
        self._remove_pending_bubble()

    def _should_show_inline_trace(self) -> bool:
        return not self.floating

    def _trace_block_width(self) -> int:
        return int(self._bubble_max_width("assistant") * 0.92)

    def _trace_insert_index(self) -> int:
        for index in range(self.message_layout.count() - 1):
            row = self.message_layout.itemAt(index).widget()
            if row is None:
                continue
            for label in row.findChildren(QtWidgets.QLabel):
                name = label.objectName()
                if name == "AiBubblePending":
                    return index
                if name == "AiBubbleAssistant" and self._streaming_bubble is not None and label is self._streaming_bubble:
                    return index
        for index in range(self.message_layout.count() - 2, -1, -1):
            row = self.message_layout.itemAt(index).widget()
            if row is None:
                continue
            for label in row.findChildren(QtWidgets.QLabel):
                if label.objectName() == "AiBubbleUser":
                    return index + 1
        return max(0, self.message_layout.count() - 1)

    def _insert_inline_trace(self, turn: TurnTrace, *, expanded: bool) -> AiInlineTraceBlock:
        block = AiInlineTraceBlock(self.engine, turn_id=turn.turn_id, parent=self.message_container)
        block.apply_turn(turn, expanded=expanded)
        block.sync_width(self._trace_block_width())

        row = QtWidgets.QWidget()
        row.setObjectName("AiTraceRow")
        if self.floating:
            row.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)
        row_layout = QtWidgets.QHBoxLayout(row)
        row_layout.setContentsMargins(2, 0, 2, 4)
        row_layout.setSpacing(0)
        row_layout.addWidget(block, 0, QtCore.Qt.AlignmentFlag.AlignLeft)
        row_layout.addStretch(1)
        self.message_layout.insertWidget(self._trace_insert_index(), row)
        return block

    def _sync_trace_block_widths(self) -> None:
        if not self._should_show_inline_trace():
            return
        width = self._trace_block_width()
        for block in self._iter_trace_blocks():
            block.sync_width(width)

    def _iter_trace_blocks(self):
        for index in range(self.message_layout.count() - 1):
            row = self.message_layout.itemAt(index).widget()
            if row is None:
                continue
            yield from row.findChildren(AiInlineTraceBlock)

    def _on_theme_changed(self, _tokens) -> None:
        """主题切换后重渲染 Markdown 气泡（HTML 内联样式不随 QSS 更新）。"""
        self._refresh_messages()

    def _refresh_messages(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            return
        self._clear_message_widgets()
        messages = self.engine.get_messages()
        turn_map = map_turns_to_user_messages(messages, self.engine.get_trace_turns())
        for index, msg in enumerate(messages):
            if msg.role not in ("user", "assistant", "error"):
                continue
            if msg.role == "assistant" and not msg.content.strip():
                continue
            if msg.role == "user":
                self._append_bubble(msg.role, msg.content, persist=False)
                turn = turn_map.get(index)
                if self._should_show_inline_trace() and turn is not None:
                    self._insert_inline_trace(turn, expanded=False)
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
        if name in ("AiBubblePending", "AiBubbleAssistant"):
            return "assistant"
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
        self._sync_trace_block_widths()

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
            bubble.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignTop)
        elif role == "error":
            bubble.setObjectName("AiBubbleError")
            bubble.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignTop)
        else:
            bubble.setObjectName("AiBubbleAssistant")
            bubble.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignTop)
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
        QtCore.QTimer.singleShot(0, lambda: self.scroll.verticalScrollBar().setValue(self.scroll.verticalScrollBar().maximum()))

    def _on_send_or_stop(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            self._on_stop()
            return
        self._on_send()

    def _on_send(self) -> None:
        text = self.input_box.toPlainText().strip()
        if not text:
            return
        if not self.engine.config.configured:
            page_notify(self, "请先在 .env 中配置 LLM_API_KEY", level="warning")
            return

        self.input_box.clear()
        self.input_box.setFixedHeight(self._input_min_height)
        self._set_busy(True)
        self._append_bubble("user", text, persist=True)
        self._show_pending_bubble("思考中…", "已收到你的问题")
        worker = ChatWorker(self.engine, text, parent=self)
        self._worker = worker
        worker.finished_ok.connect(self._on_worker_done)
        worker.cancelled.connect(self._on_worker_cancelled)
        worker.failed.connect(self._on_worker_failed)
        worker.finished.connect(worker.deleteLater)
        worker.started.connect(
            lambda: retain_thread_until_finished(self._retired_workers, worker),
            QtCore.Qt.ConnectionType.SingleShotConnection,
        )
        worker.start()

    def _on_stop(self) -> None:
        if self._worker is None or not self._worker.isRunning():
            return
        self.engine.request_cancel_stream()
        self._worker.requestInterruption()

    def _set_busy(self, busy: bool) -> None:
        self.input_box.setDisabled(busy)
        if busy:
            self.send_btn.setEnabled(True)
            self.send_btn.setText("■" if self.floating else "停止")
            self.send_btn.setToolTip("停止生成")
        else:
            self.send_btn.setText("↑" if self.floating else "发送")
            self.send_btn.setEnabled(True)
            self.send_btn.setToolTip("")
            self._stop_pending_timer()

    def _show_pending_bubble(self, main: str, sub: str = "") -> None:
        self._pending_main = main.strip() or "思考中…"
        self._pending_sub = sub.strip()
        if self._pending_bubble is None:
            bubble = QtWidgets.QLabel()
            bubble.setObjectName("AiBubblePending")
            bubble.setWordWrap(True)
            bubble.setTextFormat(QtCore.Qt.TextFormat.RichText)
            bubble.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.NoTextInteraction)
            bubble.setMinimumWidth(40)
            bubble.setMinimumHeight(36)
            bubble.setSizePolicy(
                QtWidgets.QSizePolicy.Policy.Preferred,
                QtWidgets.QSizePolicy.Policy.Preferred,
            )
            bubble.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignTop)
            self._insert_bubble_row("assistant", bubble)
            self._pending_bubble = bubble
            self._start_pending_timer()
        self._render_pending_bubble()
        self._scroll_to_bottom()

    def _render_pending_bubble(self) -> None:
        if self._pending_bubble is None:
            return
        spinner = SPINNER_FRAMES[self._pending_spinner_index % len(SPINNER_FRAMES)]
        self._pending_bubble.setText(format_pending_html(self._pending_main, self._pending_sub, spinner=spinner))
        self._sync_label_bubble(self._pending_bubble)
        if self.floating and self._tool_hint is not None:
            hint = self._pending_main
            if self._pending_sub:
                hint = f"{hint} · {self._pending_sub}"
            self._tool_hint.setText(f"⏳ {hint}")
            self._tool_hint.show()

    def _start_pending_timer(self) -> None:
        if not self._pending_timer.isActive():
            self._pending_spinner_index = 0
            self._pending_timer.start()

    def _stop_pending_timer(self) -> None:
        if self._pending_timer.isActive():
            self._pending_timer.stop()

    def _tick_pending_spinner(self) -> None:
        if self._pending_bubble is None:
            self._stop_pending_timer()
            return
        self._pending_spinner_index = (self._pending_spinner_index + 1) % len(SPINNER_FRAMES)
        self._render_pending_bubble()

    def _remove_pending_bubble(self) -> None:
        self._stop_pending_timer()
        if self._pending_bubble is None:
            return
        row = self._pending_bubble.parentWidget()
        if row is not None:
            row.deleteLater()
        else:
            self._pending_bubble.deleteLater()
        self._pending_bubble = None
        if self.floating and self._tool_hint is not None:
            self._tool_hint.hide()

    def _update_pending_from_trace(self) -> None:
        if self._pending_bubble is None:
            return
        main, sub = pending_status_from_turn(self.engine.get_current_trace_turn())
        if main == self._pending_main and sub == self._pending_sub:
            return
        self._pending_main = main
        self._pending_sub = sub
        self._render_pending_bubble()

    def _on_trace_changed(self) -> None:
        self._update_pending_from_trace()
        if not self._should_show_inline_trace():
            return
        turn = self.engine.get_current_trace_turn()
        if turn is not None:
            if self._live_trace_block is None:
                self._live_trace_block = self._insert_inline_trace(turn, expanded=True)
            else:
                self._live_trace_block.apply_turn(turn, expanded=True)
            self._scroll_to_bottom()
            return
        if self._live_trace_block is not None:
            turns = self.engine.get_trace_turns()
            if turns:
                self._live_trace_block.apply_turn(turns[-1], expanded=True)
        if self._worker is None or not self._worker.isRunning():
            self._live_trace_block = None

    def _on_stream_started(self) -> None:
        if self._pending_bubble is None:
            self._show_pending_bubble("思考中…", "已收到你的问题")
        else:
            self._update_pending_from_trace()

    def _ensure_streaming_bubble(self, initial: str) -> None:
        if self._streaming_bubble is not None:
            return
        self._streaming_bubble = self._append_bubble("assistant", initial, persist=True)

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
        if not delta:
            return
        if self._pending_bubble is not None:
            self._remove_pending_bubble()
        if self._streaming_bubble is None:
            self._ensure_streaming_bubble(delta)
        else:
            self._append_stream_delta(delta)
        self._scroll_to_bottom()

    def _on_stream_finished(self) -> None:
        self._remove_pending_bubble()
        if self._streaming_bubble is not None:
            self._sync_all_bubble_widths()
        self._streaming_bubble = None

    def _on_stream_cancelled(self) -> None:
        self._remove_pending_bubble()
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
        self._remove_pending_bubble()
        self._remove_streaming_bubble()
        self._append_bubble("error", f"生成失败：{message}", persist=True)

    def _on_tool_call_started(self, name: str) -> None:
        display = tool_display_name(name)
        self._active_tool_name = name
        self._slow_tool_timer.stop()
        self._slow_tool_timer.start()
        if self.floating and self._tool_hint is not None:
            self._tool_hint.setText(f"⏳ 正在 {display}…")
            self._tool_hint.show()
        else:
            self.tools_status_bar.show_progress(f"正在 {display}…")

    def _on_tool_call_slow(self) -> None:
        name = self._active_tool_name
        if not name:
            return
        display = tool_display_name(name)
        slow_msg = f"⏳ {display} 耗时较长，仍在执行…"
        if self.floating and self._tool_hint is not None:
            self._tool_hint.setText(slow_msg)
            self._tool_hint.show()
        else:
            self.tools_status_bar.show_progress(slow_msg)

    def _on_tool_call_finished(self, name: str) -> None:
        self._slow_tool_timer.stop()
        self._active_tool_name = ""
        if self.floating and self._tool_hint is not None:
            self._tool_hint.hide()
        else:
            self.tools_status_bar.hide_progress()

    def _on_worker_done(self) -> None:
        self._worker = None
        self._remove_pending_bubble()
        self._set_busy(False)
        self._live_trace_block = None
        self._refresh_messages()

    def _on_worker_cancelled(self) -> None:
        self._worker = None
        self._remove_pending_bubble()
        self._set_busy(False)
        self._live_trace_block = None
        self._refresh_messages()

    def _on_worker_failed(self, message: str) -> None:
        self._worker = None
        self._remove_pending_bubble()
        self._set_busy(False)
        if message:
            self._append_bubble("error", message, persist=True)

    def _on_clear(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            return
        if confirm_action(
            self,
            "确认",
            "清空当前会话的所有消息？",
            confirm_text="清空",
            destructive=True,
        ):
            self.engine.clear_session()

    def _on_new_session(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            return
        self.engine.new_session()

    def _on_show_sessions(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            page_notify(self, "请等待当前回复完成后再切换会话")
            return
        if self.engine.is_busy():
            page_notify(self, "请等待当前回复完成后再切换会话")
            return
        show_ai_session_dialog(self.engine, self)

    def _on_tools_status_changed(self, snapshot: ToolsStatusSnapshot) -> None:
        self.tools_status_bar.apply_snapshot(snapshot)

    def _on_show_tools(self) -> None:
        dialog = AiToolsDialog(self.engine, self)
        dialog.reload_requested.connect(lambda: self._on_tools_status_changed(self.engine.get_tools_status()))
        dialog.exec()

    def _on_reload_tools(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            page_notify(self, "请等待当前回复完成后再重新加载")
            return
        self.engine.reload_tools()

    def _on_reload_llm_config(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            page_notify(self, "请等待当前回复完成后再重载配置")
            return
        cfg = self.engine.reload_config()
        self._update_model_action()
        if cfg.configured:
            page_notify(
                self,
                f"LLM 已重载：{cfg.model} · {cfg.api_base} · Key {cfg.masked_key()}",
                level="success",
            )
        else:
            page_notify(self, "未检测到 LLM_API_KEY，请编辑 .env 后再次重载。", level="warning")

    def _on_input_enter(self, newline: bool) -> None:
        if newline:
            if self._completion_popup.isVisible():
                self._completion_popup.hide()
            self._insert_input_newline()
            return
        if self._completion_popup.isVisible() and self._completion_popup.hasFocus():
            row = self._completion_popup.currentRow()
            if row < 0:
                row = 0
            item = self._completion_popup.item(row)
            if item is not None:
                self._on_completion_selected(item)
            return
        self._completion_popup.hide()
        self._on_send_or_stop()

    def _handle_input_return(self, key_event: QtGui.QKeyEvent) -> bool:
        if key_event.key() not in (
            QtCore.Qt.Key.Key_Return,
            QtCore.Qt.Key.Key_Enter,
        ):
            return False
        mods = key_event.modifiers()
        newline = bool(mods & (QtCore.Qt.KeyboardModifier.ControlModifier | QtCore.Qt.KeyboardModifier.MetaModifier))
        self._on_input_enter(newline)
        return True

    def eventFilter(self, obj: QtCore.QObject, event: QtCore.QEvent) -> bool:
        if obj is self.scroll.viewport() and event.type() == QtCore.QEvent.Type.Resize:
            self.message_container.setMinimumWidth(self._message_viewport_width())
            self._sync_all_bubble_widths()
        input_targets = (self.input_box, self.input_box.viewport())
        if obj in input_targets and event.type() == QtCore.QEvent.Type.KeyPress:
            key_event = event
            if isinstance(key_event, QtGui.QKeyEvent):
                if obj is self.input_box.viewport() and self._handle_input_return(key_event):
                    return True
                if self._completion_popup.isVisible():
                    if key_event.key() == QtCore.Qt.Key.Key_Down:
                        self._completion_popup.setFocus()
                        self._completion_popup.setCurrentRow(0)
                        return True
                    if key_event.key() == QtCore.Qt.Key.Key_Escape:
                        self._completion_popup.hide()
                        return True
        return super().eventFilter(obj, event)

    def _insert_input_newline(self) -> None:
        cursor = self.input_box.textCursor()
        cursor.insertText("\n")
        self.input_box.setTextCursor(cursor)

    def showEvent(self, event: QtGui.QShowEvent) -> None:
        super().showEvent(event)
        QtCore.QTimer.singleShot(0, self._on_panel_shown)

    def _on_panel_shown(self) -> None:
        self.message_container.setMinimumWidth(self._message_viewport_width())
        self._sync_all_bubble_widths()

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
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
            (signals.trace_changed, self._on_trace_changed),
        ):
            try:
                signal.disconnect(slot)
            except (RuntimeError, TypeError):
                pass

    def deactivate(self, *, final: bool = False) -> None:
        self._remove_pending_bubble()
        self._set_busy(False)
        self._completion_popup.hide()
        if final:
            self._disconnect_engine_signals()
        worker = self._worker
        self._worker = None
        if final and worker is not None:
            worker.safe_stop()
        else:
            release_thread(self._retired_workers, worker, timeout_ms=0)
        if final:
            for retired in list(self._retired_workers):
                if isinstance(retired, ChatWorker):
                    retired.safe_stop()
                else:
                    release_thread(self._retired_workers, retired, timeout_ms=2000)
