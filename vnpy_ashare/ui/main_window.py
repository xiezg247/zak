"""A 股终端主窗口：左侧菜单切换 市场 / 自选 / 本地 等功能页。"""

from __future__ import annotations

from importlib import import_module
from types import ModuleType

from vnpy.event import Event, EventEngine

from vnpy_ashare.events import EVENT_OPEN_BACKTEST, BacktestRequest
from vnpy.trader.engine import MainEngine
from vnpy.trader.ui import MainWindow
from vnpy.trader.ui.qt import QtCore, QtGui, QtWidgets

from vnpy_ashare.ai.page import AiPageWidget
from vnpy_ashare.engine import APP_NAME, AshareEngine
from vnpy_ashare.ui.nav import APP_NAV_ENTRIES, SidebarNav
from vnpy_llm.engine import APP_NAME as LLM_APP_NAME, LlmEngine
from vnpy_llm.ui.panel import AiChatPanel
from vnpy_llm.ui.tools_widgets import show_ai_tools_dialog
from vnpy_ashare.ui.page_shell import LocalPageWidget, MarketPageWidget, WatchlistPageWidget
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

    def __init__(self, main_engine: MainEngine, event_engine: EventEngine) -> None:
        self._page_widgets: dict[str, QtWidgets.QWidget] = {}
        self._current_key: str | None = None
        self._ai_dock: QtWidgets.QDockWidget | None = None
        self._ai_dock_panel: AiChatPanel | None = None
        self._ai_page_widget: AiPageWidget | None = None
        self._ai_fullscreen = False
        self._page_before_ai: int = 0
        self._ai_toggle_action: QtGui.QAction | None = None
        super().__init__(main_engine, event_engine)
        self._signal_open_backtest.connect(self._handle_open_backtest)
        self.event_engine.register(EVENT_OPEN_BACKTEST, self._on_open_backtest_event)

    def init_dock(self) -> None:
        return

    def init_toolbar(self) -> None:
        self.toolbar = QtWidgets.QToolBar(self)
        self.toolbar.setVisible(False)

    def init_ui(self) -> None:
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
        self._ai_toggle_action.triggered.connect(self._toggle_ai_dock)
        self.addAction(self._ai_toggle_action)
        tools_menu.addSeparator()
        ai_tools_action = tools_menu.addAction("AI 工具能力…")
        ai_tools_action.triggered.connect(self._open_ai_tools_dialog)
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

        self._init_ai_dock()
        self.setCentralWidget(shell)
        self._show_page(0)

    def _get_llm_engine(self) -> LlmEngine | None:
        engine = self.main_engine.get_engine(LLM_APP_NAME)
        if isinstance(engine, LlmEngine):
            return engine
        return None

    def _open_ai_tools_dialog(self) -> None:
        llm_engine = self._get_llm_engine()
        if llm_engine is None:
            QtWidgets.QMessageBox.warning(self, "提示", "AI 助手未加载，请确认已安装并启用 vnpy_llm")
            return
        show_ai_tools_dialog(llm_engine, self)

    def _init_ai_dock(self) -> bool:
        if self._ai_dock is not None:
            return True

        llm_engine = self._get_llm_engine()
        if llm_engine is None:
            return False

        panel = AiChatPanel(llm_engine, compact=True, parent=self)
        panel.expand_requested.connect(self._enter_ai_fullscreen)
        self._ai_dock_panel = panel

        dock = QtWidgets.QDockWidget("AI 助手", self)
        dock.setObjectName("AiDock")
        dock.setWidget(panel)
        dock.setFeatures(
            QtWidgets.QDockWidget.DockWidgetFeature.DockWidgetClosable
            | QtWidgets.QDockWidget.DockWidgetFeature.DockWidgetMovable
        )
        dock.setAllowedAreas(
            QtCore.Qt.DockWidgetArea.LeftDockWidgetArea
            | QtCore.Qt.DockWidgetArea.RightDockWidgetArea
        )
        dock.setMinimumWidth(320)
        self.addDockWidget(QtCore.Qt.DockWidgetArea.RightDockWidgetArea, dock)
        dock.hide()
        self._ai_dock = dock
        return True

    def _ensure_ai_dock(self) -> bool:
        if self._init_ai_dock():
            return True
        QtWidgets.QMessageBox.warning(self, "提示", "AI 助手未加载，请确认已安装并启用 vnpy_llm")
        return False

    def _ai_dock_visible(self) -> bool:
        return self._ai_dock is not None and self._ai_dock.isVisible()

    def _hide_ai_dock(self) -> None:
        if self._ai_dock is not None:
            self._ai_dock.hide()

    def _show_ai_dock(self) -> None:
        if self._ai_dock is None:
            return
        self._ai_dock.setVisible(True)
        self._ai_dock.show()
        self._ai_dock.raise_()
        self.resizeDocks(
            [self._ai_dock],
            [360],
            QtCore.Qt.Orientation.Horizontal,
        )
        if self._ai_dock_panel is not None:
            self._ai_dock_panel.focus_input()

    def _remember_page_before_ai(self) -> None:
        if self._ai_fullscreen:
            return
        if self._current_key:
            index = self._nav_index_for_key(self._current_key)
            if index is not None:
                self._page_before_ai = index

    def _toggle_ai_dock(self) -> None:
        if not self._ensure_ai_dock():
            return
        if self._ai_fullscreen:
            self._return_to_dock_mode()
            return
        if self._ai_dock_visible():
            self._hide_ai_dock()
        else:
            self._show_ai_dock()

    def _return_to_dock_mode(self) -> None:
        if self._ai_fullscreen:
            self._leave_ai_fullscreen()
        self._show_page(self._page_before_ai)
        self._show_ai_dock()

    def _get_or_create_ai_page(self) -> AiPageWidget:
        if self._ai_page_widget is None:
            page = AiPageWidget(self.main_engine, self.event_engine)
            page.collapse_to_dock.connect(self._return_to_dock_mode)
            self._ai_page_widget = page
            self.stack.addWidget(page)
        return self._ai_page_widget

    def _enter_ai_fullscreen(self) -> None:
        self._remember_page_before_ai()
        self._hide_ai_dock()
        page = self._get_or_create_ai_page()
        self.stack.setCurrentWidget(page)
        page.activate()
        self._ai_fullscreen = True
        self.sidebar.set_active_index(self._page_before_ai)

    def _leave_ai_fullscreen(self) -> None:
        if not self._ai_fullscreen:
            return
        self._ai_fullscreen = False
        if self._ai_page_widget is not None:
            self._ai_page_widget.deactivate()

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

    def _nav_index_for_key(self, key: str) -> int | None:
        for index, entry in enumerate(APP_NAV_ENTRIES):
            if entry.key == key:
                return index
        return None

    def _on_nav_changed(self, index: int) -> None:
        if self._ai_fullscreen:
            self._leave_ai_fullscreen()
        self._show_page(index)

    def _show_page(self, index: int) -> None:
        entry = self.sidebar.entry_at(index)
        widget = self._get_or_create_page(entry.key)
        if widget is None:
            return

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
        if self._ai_dock_panel is not None:
            self._ai_dock_panel.deactivate()
        if self._ai_page_widget is not None:
            self._ai_page_widget.deactivate()
        for widget in self._page_widgets.values():
            if hasattr(widget, "deactivate"):
                widget.deactivate()
        super().closeEvent(event)
