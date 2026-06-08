"""A 股终端主窗口：左侧菜单切换 市场 / 自选 / 本地 等功能页。"""

from __future__ import annotations

from importlib import import_module
from types import ModuleType

from vnpy.event import Event, EventEngine

from vnpy_ashare.events import (
    EVENT_ASK_AI,
    EVENT_FILL_SCREENER,
    EVENT_OPEN_BACKTEST,
    EVENT_OPEN_BATCH_BACKTEST,
    AskAiRequest,
    BacktestRequest,
    BatchBacktestViewRequest,
    FillScreenerRequest,
)
from vnpy.trader.engine import MainEngine
from vnpy.trader.ui import MainWindow
from vnpy.trader.ui.qt import QtCore, QtGui, QtWidgets

from vnpy_ashare.ai.page import AiPageWidget
from vnpy_ashare.branding import window_title as build_window_title
from vnpy_ashare.engine import APP_NAME, AshareEngine
from vnpy_ashare.ui.nav import APP_NAV_ENTRIES, SidebarNav
from vnpy_llm.engine import APP_NAME as LLM_APP_NAME, LlmEngine
from vnpy_llm.ui.floating_panel import FloatingAiButton, FloatingAiPanel, BTN_MARGIN
from vnpy_llm.ui.tools_widgets import show_ai_tools_dialog
from vnpy_llm.ui.tool_audit_dialog import show_ai_tool_audit_dialog
from vnpy_ashare.ui.batch_backtest_page import BatchBacktestPageWidget
from vnpy_ashare.ui.page_shell import LocalPageWidget, MarketPageWidget, WatchlistPageWidget
from vnpy_ashare.ui.screener_page import ScreenerPageWidget
from vnpy_ashare.ui.scheduler_dialog import SchedulerDialog
from vnpy_ashare.ui.styles import TERMINAL_STYLESHEET

_QUOTES_WIDGETS: dict[str, type[QtWidgets.QWidget]] = {
    "market": MarketPageWidget,
    "watchlist": WatchlistPageWidget,
    "local": LocalPageWidget,
}

_VNPY_WIDGETS: dict[str, tuple[str, str]] = {
    "cta_backtest": ("vnpy_ashare.ui.backtest_widget", "BacktesterWidget"),
    "data_manager": ("vnpy_ashare.ui.manager_widget", "ManagerWidget"),
}


class AshareMainWindow(MainWindow):
    """左侧图标菜单 + 中央内容区，不再使用顶部「功能」菜单。"""

    # EventEngine 在后台线程回调，须经 Signal 切回 GUI 线程再操作控件。
    _signal_open_backtest = QtCore.Signal(object)
    _signal_open_batch_backtest = QtCore.Signal(object)
    _signal_fill_screener = QtCore.Signal(object)
    _signal_ask_ai = QtCore.Signal(object)

    def __init__(self, main_engine: MainEngine, event_engine: EventEngine) -> None:
        self._page_widgets: dict[str, QtWidgets.QWidget] = {}
        self._current_key: str | None = None
        self._floating_ai_btn: FloatingAiButton | None = None
        self._floating_ai_panel: FloatingAiPanel | None = None
        self._page_before_ai: int = 0
        self._ai_toggle_action: QtGui.QAction | None = None
        self._screener_draft_connected = False
        super().__init__(main_engine, event_engine)
        self._signal_open_backtest.connect(self._handle_open_backtest)
        self._signal_open_batch_backtest.connect(self._handle_open_batch_backtest)
        self._signal_fill_screener.connect(self._handle_fill_screener)
        self._signal_ask_ai.connect(self._handle_ask_ai)
        self.event_engine.register(EVENT_OPEN_BACKTEST, self._on_open_backtest_event)
        self.event_engine.register(EVENT_OPEN_BATCH_BACKTEST, self._on_open_batch_backtest_event)
        self.event_engine.register(EVENT_FILL_SCREENER, self._on_fill_screener_event)
        self.event_engine.register(EVENT_ASK_AI, self._on_ask_ai_event)

    def init_dock(self) -> None:
        return

    def init_toolbar(self) -> None:
        self.toolbar = QtWidgets.QToolBar(self)
        self.toolbar.setVisible(False)

    def init_ui(self) -> None:
        self.window_title = build_window_title()
        self.setWindowTitle(self.window_title)
        self.init_toolbar()
        self.init_menu()
        self._init_shell()
        self.load_window_setting("custom")

    def init_menu(self) -> None:
        super().init_menu()
        bar = self.menuBar()
        for action in bar.actions():
            text = action.text().replace("&", "")
            if text in ("功能", "Func"):
                bar.removeAction(action)
                break

        tools_menu = bar.addMenu("工具")
        self._ai_toggle_action = tools_menu.addAction("切换 AI 侧栏")
        self._ai_toggle_action.setShortcuts([
            QtGui.QKeySequence("Ctrl+L"),
            QtGui.QKeySequence("Meta+L"),
        ])
        self._ai_toggle_action.triggered.connect(self._toggle_floating_ai)
        self.addAction(self._ai_toggle_action)
        tools_menu.addSeparator()
        ai_tools_action = tools_menu.addAction("AI 工具能力…")
        ai_tools_action.triggered.connect(self._open_ai_tools_dialog)
        audit_action = tools_menu.addAction("AI 工具审计…")
        audit_action.triggered.connect(self._open_ai_tool_audit_dialog)
        tools_menu.addSeparator()

        scheduler_action = tools_menu.addAction("定时任务...")
        scheduler_action.triggered.connect(self._open_scheduler_dialog)

        quick_menu = tools_menu.addMenu("立即执行")
        quick_menu.addAction("行情采集", lambda: self._run_scheduler_job("collect_quotes"))
        quick_menu.addAction("同步 A 股列表", lambda: self._run_scheduler_job("sync_universe"))
        quick_menu.addAction("下载自选日 K", lambda: self._run_scheduler_job("batch_download"))

    def _get_ashare_engine(self) -> AshareEngine | None:
        engine = self.main_engine.get_engine(APP_NAME)
        if isinstance(engine, AshareEngine):
            return engine
        return None

    def _open_scheduler_dialog(self) -> None:
        ashare_engine = self._get_ashare_engine()
        if ashare_engine is None:
            QtWidgets.QMessageBox.warning(self, "提示", "A 股引擎未加载")
            return
        dialog = SchedulerDialog(ashare_engine.scheduler, self)
        dialog.exec()

    def _run_scheduler_job(self, job_id: str) -> None:
        ashare_engine = self._get_ashare_engine()
        if ashare_engine is None:
            QtWidgets.QMessageBox.warning(self, "提示", "A 股引擎未加载")
            return
        if not ashare_engine.scheduler.run_now(job_id):
            QtWidgets.QMessageBox.information(self, "提示", "任务正在运行中")

    def _init_shell(self) -> None:
        self.sidebar = SidebarNav(APP_NAV_ENTRIES, self)
        self.sidebar.page_changed.connect(self._on_nav_changed)

        self.stack = QtWidgets.QStackedWidget()
        self.stack.setObjectName("MainStack")

        body = QtWidgets.QHBoxLayout()
        body.setSpacing(0)
        body.setContentsMargins(0, 0, 0, 0)
        body.addWidget(self.sidebar)
        body.addWidget(self.stack, stretch=1)

        shell = QtWidgets.QWidget()
        shell.setLayout(body)
        shell.setStyleSheet(TERMINAL_STYLESHEET)

        self._init_floating_ai()
        self.setCentralWidget(shell)
        self._show_page(0)

    def _get_llm_engine(self) -> LlmEngine | None:
        engine = self.main_engine.get_engine(LLM_APP_NAME)
        if isinstance(engine, LlmEngine):
            self._ensure_screener_draft_handler(engine)
            return engine
        return None

    def _ensure_screener_draft_handler(self, engine: LlmEngine) -> None:
        if self._screener_draft_connected:
            return
        engine.signals.screener_draft_ready.connect(self._on_screener_draft_ready)
        self._screener_draft_connected = True

    def _on_screener_draft_ready(self, draft_id: str) -> None:
        from vnpy_ashare.ui.screener_confirm_dialog import show_screener_confirm_dialog

        engine = self.main_engine.get_engine(LLM_APP_NAME)
        if not isinstance(engine, LlmEngine):
            return
        show_screener_confirm_dialog(draft_id, engine, parent=self)

    def _open_ai_tools_dialog(self) -> None:
        llm_engine = self._get_llm_engine()
        if llm_engine is None:
            QtWidgets.QMessageBox.warning(self, "提示", "AI 助手未加载，请确认已安装并启用 vnpy_llm")
            return
        show_ai_tools_dialog(llm_engine, self)

    def _open_ai_tool_audit_dialog(self) -> None:
        llm_engine = self._get_llm_engine()
        if llm_engine is None:
            QtWidgets.QMessageBox.warning(self, "提示", "AI 助手未加载，请确认已安装并启用 vnpy_llm")
            return
        show_ai_tool_audit_dialog(llm_engine, self)

    def _init_floating_ai(self) -> bool:
        """创建浮动按钮与弹出面板。"""
        if self._floating_ai_btn is not None:
            return True

        llm_engine = self._get_llm_engine()
        if llm_engine is None:
            return False

        # 悬浮按钮（右下角）
        shell = self.centralWidget()
        btn = FloatingAiButton(shell)
        btn.clicked_toggle.connect(self._toggle_floating_ai)
        btn.raise_()
        self._floating_ai_btn = btn

        # 弹出面板
        panel = FloatingAiPanel(llm_engine, parent=None)
        panel.expand_requested.connect(self._open_ai_page)
        self._floating_ai_panel = panel

        self._position_floating_button()
        return True

    def _ensure_floating_ai(self) -> bool:
        if self._init_floating_ai():
            return True
        QtWidgets.QMessageBox.warning(self, "提示", "AI 助手未加载，请确认已安装并启用 vnpy_llm")
        return False

    def _floating_ai_visible(self) -> bool:
        return self._floating_ai_panel is not None and self._floating_ai_panel.isVisible()

    def _hide_floating_ai(self) -> None:
        if self._floating_ai_panel is not None:
            self._floating_ai_panel.hide()

    def _show_floating_ai(self) -> None:
        if self._floating_ai_panel is None:
            return
        self._floating_ai_panel.show_near(self)
        self._floating_ai_panel.focus_input()

    def _toggle_floating_ai(self) -> None:
        if not self._ensure_floating_ai():
            return
        if self._current_key == "ai_assistant":
            self._return_to_floating_mode()
            return
        if self._floating_ai_visible():
            self._hide_floating_ai()
        else:
            self._show_floating_ai()

    def _return_to_floating_mode(self) -> None:
        self._show_page(self._page_before_ai)
        self._show_floating_ai()

    def _position_floating_button(self) -> None:
        """将浮动按钮定位到内容区右下角。"""
        btn = self._floating_ai_btn
        if btn is None:
            return
        shell = btn.parentWidget()
        if shell is None:
            return
        btn.move(
            shell.width() - btn.width() - BTN_MARGIN,
            shell.height() - btn.height() - BTN_MARGIN,
        )
        btn.raise_()

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:
        super().resizeEvent(event)
        self._position_floating_button()

    def _open_ai_page(self) -> None:
        index = self._nav_index_for_key("ai_assistant")
        if index is None:
            return
        if self._get_llm_engine() is None:
            QtWidgets.QMessageBox.warning(self, "提示", "AI 助手未加载，请确认已安装并启用 vnpy_llm")
            return
        self._show_page(index)

    def _on_open_backtest_event(self, event: Event) -> None:
        """EventEngine 线程：仅转发，不触碰 Qt 控件。"""
        if isinstance(event.data, BacktestRequest):
            self._signal_open_backtest.emit(event.data)

    def _handle_open_backtest(self, data: BacktestRequest) -> None:
        """GUI 主线程：切换页面并预填回测代码。"""
        index = self._nav_index_for_key("cta_backtest")
        if index is None:
            return
        self._show_page(index)
        widget = self._page_widgets.get("cta_backtest")
        if widget is not None and hasattr(widget, "apply_vt_symbol"):
            widget.apply_vt_symbol(data.vt_symbol, source_page=data.source_page)

    def _on_open_batch_backtest_event(self, event: Event) -> None:
        if isinstance(event.data, BatchBacktestViewRequest):
            self._signal_open_batch_backtest.emit(event.data)

    def _handle_open_batch_backtest(self, data: BatchBacktestViewRequest) -> None:
        index = self._nav_index_for_key("batch_backtest")
        if index is None:
            return
        self._show_page(index)
        widget = self._page_widgets.get("batch_backtest")
        if widget is not None and hasattr(widget, "show_batch"):
            widget.show_batch(data.batch_id)

    def _on_fill_screener_event(self, event: Event) -> None:
        if isinstance(event.data, FillScreenerRequest):
            self._signal_fill_screener.emit(event.data)

    def _handle_fill_screener(self, data: FillScreenerRequest) -> None:
        index = self._nav_index_for_key("screener")
        if index is None:
            return
        self._show_page(index)
        widget = self._page_widgets.get("screener")
        if widget is not None and hasattr(widget, "apply_request"):
            widget.apply_request(data)

    def _on_ask_ai_event(self, event: Event) -> None:
        if isinstance(event.data, AskAiRequest):
            self._signal_ask_ai.emit(event.data)

    def _handle_ask_ai(self, data: AskAiRequest) -> None:
        if data.use_full_page:
            if self._get_llm_engine() is None:
                QtWidgets.QMessageBox.warning(self, "提示", "AI 助手未加载，请确认已安装并启用 vnpy_llm")
                return
            index = self._nav_index_for_key("ai_assistant")
            if index is None:
                return
            self._show_page(index)
            widget = self._page_widgets.get("ai_assistant")
            if widget is not None and hasattr(widget, "set_input_text"):
                widget.set_input_text(data.prompt)
            return
        if not self._ensure_floating_ai():
            return
        self._show_floating_ai()
        if self._floating_ai_panel is not None:
            self._floating_ai_panel.set_input_text(data.prompt)

    def _nav_index_for_key(self, key: str) -> int | None:
        for index, entry in enumerate(APP_NAV_ENTRIES):
            if entry.key == key:
                return index
        return None

    def _on_nav_changed(self, index: int) -> None:
        entry = self.sidebar.entry_at(index)
        if entry.key == "ai_assistant" and self._get_llm_engine() is None:
            QtWidgets.QMessageBox.warning(self, "提示", "AI 助手未加载，请确认已安装并启用 vnpy_llm")
            if self._current_key:
                prev = self._nav_index_for_key(self._current_key)
                if prev is not None:
                    self.sidebar.set_active_index(prev)
            return
        self._show_page(index)

    def _show_page(self, index: int) -> None:
        entry = self.sidebar.entry_at(index)
        widget = self._get_or_create_page(entry.key)
        if widget is None:
            return

        if entry.key == "ai_assistant":
            if self._current_key and self._current_key != "ai_assistant":
                prev_index = self._nav_index_for_key(self._current_key)
                if prev_index is not None:
                    self._page_before_ai = prev_index
            self._hide_floating_ai()

        if self._current_key and self._current_key != entry.key:
            old = self._page_widgets.get(self._current_key)
            if old is not None and hasattr(old, "deactivate"):
                old.deactivate()

        if self.stack.indexOf(widget) < 0:
            self.stack.addWidget(widget)
        self.stack.setCurrentWidget(widget)

        if hasattr(widget, "activate"):
            widget.activate()

        self._current_key = entry.key
        if entry.key != "ai_assistant":
            self._page_before_ai = index
        self.sidebar.set_active_index(index)
        self.raise_()
        self.activateWindow()

    def _get_or_create_page(self, key: str) -> QtWidgets.QWidget | None:
        if key in self._page_widgets:
            return self._page_widgets[key]

        widget: QtWidgets.QWidget | None = None

        if key in _QUOTES_WIDGETS:
            widget = _QUOTES_WIDGETS[key](self.main_engine, self.event_engine)
        elif key in _VNPY_WIDGETS:
            module_path, class_name = _VNPY_WIDGETS[key]
            ui_module: ModuleType = import_module(module_path)
            widget_class = getattr(ui_module, class_name)
            widget = widget_class(self.main_engine, self.event_engine)
        elif key == "ai_assistant":
            page = AiPageWidget(self.main_engine, self.event_engine)
            page.collapse_to_dock.connect(self._return_to_floating_mode)
            widget = page
        elif key == "screener":
            widget = ScreenerPageWidget(self.main_engine, self.event_engine)
        elif key == "batch_backtest":
            widget = BatchBacktestPageWidget(self.main_engine, self.event_engine)

        if widget is not None:
            self._page_widgets[key] = widget
            self.widgets[key] = widget

        return widget

    def open_widget(self, widget_class: type[QtWidgets.QWidget], name: str) -> None:
        name_map = {
            "Ashare": "watchlist",
            "CtaBacktester": "cta_backtest",
            "DataManager": "data_manager",
        }
        key = name_map.get(name)
        if key:
            for index, entry in enumerate(APP_NAV_ENTRIES):
                if entry.key == key:
                    self._show_page(index)
                    return
        super().open_widget(widget_class, name)

    def load_window_setting(self, name: str) -> None:
        settings = QtCore.QSettings(self.window_title, name)
        geometry = settings.value("geometry")
        if geometry is not None:
            self.restoreGeometry(geometry)

    def save_window_setting(self, name: str) -> None:
        settings = QtCore.QSettings(self.window_title, name)
        settings.setValue("geometry", self.saveGeometry())

    def closeEvent(self, event) -> None:
        if self._floating_ai_panel is not None:
            self._floating_ai_panel.deactivate()
        for widget in self._page_widgets.values():
            if hasattr(widget, "deactivate"):
                widget.deactivate()
        super().closeEvent(event)
