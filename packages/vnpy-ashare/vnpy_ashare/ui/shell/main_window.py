"""A 股终端主窗口：左侧菜单切换 市场 / 自选 / 本地 等功能页。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vnpy.event import EventEngine
from vnpy.trader.engine import MainEngine
from vnpy.trader.ui import MainWindow
from vnpy.trader.ui.qt import QtCore, QtGui, QtWidgets

from vnpy_ashare.app.branding import window_title as build_window_title
from vnpy_ashare.app.deferred_apps import ensure_cta_backtester_app, ensure_data_manager_app
from vnpy_ashare.app.events import (
    EVENT_AI_ACTION,
    EVENT_ASK_AI,
    EVENT_FILL_SCREENER,
    EVENT_OPEN_BACKTEST,
    EVENT_OPEN_BATCH_BACKTEST,
    EVENT_ORB_ATTENTION,
)
from vnpy_ashare.config.preferences._settings import (
    read_setting_value,
    write_setting_value,
)
from vnpy_ashare.ui.shell.floating_controller import FloatingAiController
from vnpy_ashare.ui.shell.main_window_ai_events import (
    AI_NOT_LOADED_MSG,
    get_llm_engine,
    handle_ai_action,
    handle_ask_ai,
    handle_open_backtest,
    handle_open_batch_backtest,
    handle_orb_attention,
    on_ai_action_event,
    on_ask_ai_event,
    on_fill_screener_event,
    on_open_backtest_event,
    on_open_batch_backtest_event,
    on_orb_attention_event,
    open_ai_page,
    open_ai_tool_audit_dialog,
    open_ai_tools_dialog,
)
from vnpy_ashare.ui.shell.main_window_ai_events import (
    handle_fill_screener as _handle_fill_screener,
)
from vnpy_ashare.ui.shell.main_window_navigation import (
    focus_watchlist_symbol,
    navigate_to_page,
    open_market_concept_drilldown,
    open_market_industry_filter,
    open_radar_card,
    open_radar_leader_loop,
    open_screener_industry,
    open_screener_leader_screen,
    open_screener_radar_resonance,
    open_screener_run,
    open_sector_flow,
)
from vnpy_ashare.ui.shell.main_window_pages import (
    QUOTES_WIDGETS,
    get_or_create_page,
    nav_index_for_key,
    open_backstage_dialog,
    open_backtest_menu_dialog,
    open_data_manager_dialog,
    open_local_data_dialog,
    open_notes_center_dialog,
    open_scheduler_dialog,
    show_page_by_key,
    try_open_vnpy_widget,
)
from vnpy_ashare.ui.shell.main_window_scheduler import (
    bind_scheduler_notifications,
    handle_scheduler_job,
    on_scheduler_job_event,
    refresh_info_feed_badge,
    schedule_deferred_radar_prewarm,
    schedule_deferred_scheduler_start,
    schedule_deferred_shell_extras,
    schedule_deferred_watchlist_prewarm,
)
from vnpy_ashare.ui.shell.nav import (
    APP_NAV_GROUPS,
    BACKSTAGE_ENTRIES,
    BACKTEST_ENTRIES,
    SidebarNav,
)
from vnpy_ashare.ui.shell.settings.dialog import show_settings_dialog
from vnpy_ashare.ui.shell.shortcuts import (
    BACKSTAGE_SHORTCUTS,
    BACKTEST_SHORTCUTS,
    NOTES_CENTER_SHORTCUT,
    bind_main_window_shortcuts,
    format_shortcuts_help,
)
from vnpy_common.startup_profile import profiler
from vnpy_common.ui.feedback import PageToastHost, page_notify, show_info_dialog
from vnpy_common.ui.qt_helpers import restore_geometry_on_screen
from vnpy_common.ui.theme.manager import theme_manager

if TYPE_CHECKING:
    from vnpy_llm.app.engine import LlmEngine


class AshareMainWindow(MainWindow):
    """左侧图标菜单 + 中央内容区，不再使用顶部「功能」「微信」「帮助」菜单。"""

    _signal_open_backtest = QtCore.Signal(object)
    _signal_open_batch_backtest = QtCore.Signal(object)
    _signal_fill_screener = QtCore.Signal(object)
    _signal_ask_ai = QtCore.Signal(object)
    _signal_orb_attention = QtCore.Signal(object)
    _signal_ai_action = QtCore.Signal(object)
    _signal_scheduler_job = QtCore.Signal(str)

    def __init__(self, main_engine: MainEngine, event_engine: EventEngine) -> None:
        self._page_widgets: dict[str, QtWidgets.QWidget] = {}
        self._current_key: str | None = None
        self._floating_controller: FloatingAiController | None = None
        self._page_before_ai: int = 0
        self._ai_toggle_action: QtGui.QAction | None = None
        self._scheduler_listener_connected = False
        self._initial_page_scheduled = False
        self._scheduler_deferred_scheduled = False
        self._shell_extras_scheduled = False
        self._watchlist_prewarm_scheduled = False
        self._theme_manager = theme_manager()
        self._theme_dark_action: QtGui.QAction | None = None
        self._theme_light_action: QtGui.QAction | None = None
        self._theme_system_action: QtGui.QAction | None = None
        with profiler.phase("main_window.super"):
            super().__init__(main_engine, event_engine)
        with profiler.phase("main_window.events"):
            self._wire_window_events()

    def _wire_window_events(self) -> None:
        self._signal_open_backtest.connect(lambda data: handle_open_backtest(self, data))
        self._signal_open_batch_backtest.connect(lambda data: handle_open_batch_backtest(self, data))
        self._signal_fill_screener.connect(lambda data: _handle_fill_screener(self, data))
        self._signal_ask_ai.connect(lambda data: handle_ask_ai(self, data))
        self._signal_orb_attention.connect(lambda data: handle_orb_attention(self, data))
        self._signal_ai_action.connect(lambda data: handle_ai_action(self, data))
        self._signal_scheduler_job.connect(lambda job_id: handle_scheduler_job(self, job_id))
        self.event_engine.register(EVENT_OPEN_BACKTEST, lambda e: on_open_backtest_event(self, e))
        self.event_engine.register(EVENT_OPEN_BATCH_BACKTEST, lambda e: on_open_batch_backtest_event(self, e))
        self.event_engine.register(EVENT_FILL_SCREENER, lambda e: on_fill_screener_event(self, e))
        self.event_engine.register(EVENT_ASK_AI, lambda e: on_ask_ai_event(self, e))
        self.event_engine.register(EVENT_ORB_ATTENTION, lambda e: on_orb_attention_event(self, e))
        self.event_engine.register(EVENT_AI_ACTION, lambda e: on_ai_action_event(self, e))

    def init_dock(self) -> None:
        """不使用 vnpy 默认 Dock（交易/日志面板）。"""

    def init_toolbar(self) -> None:
        self.toolbar = QtWidgets.QToolBar(self)
        self.toolbar.setVisible(False)

    def init_ui(self) -> None:
        with profiler.phase("main_window.title"):
            self.window_title = build_window_title()
            self.setWindowTitle(self.window_title)
            self.init_dock()
            self.init_toolbar()
        with profiler.phase("main_window.theme_menu"):
            self._theme_manager.load_saved()
            self.init_menu()
        with profiler.phase("main_window.shell"):
            self._init_shell()
        with profiler.phase("main_window.shortcuts"):
            self._bind_nav_shortcuts()
            self.load_window_setting("custom")

    def init_menu(self) -> None:
        bar = self.menuBar()
        bar.setNativeMenuBar(False)

        sys_menu = bar.addMenu("系统")
        exit_action = sys_menu.addAction("退出")
        exit_action.triggered.connect(self.close)

        setting_action = QtGui.QAction("配置", self)
        setting_action.triggered.connect(self.edit_global_setting)
        bar.addAction(setting_action)

        backstage_menu = bar.addMenu("后台")
        for entry in BACKSTAGE_ENTRIES:
            action = backstage_menu.addAction(f"{entry.label}…")
            action.triggered.connect(lambda _checked=False, key=entry.key: open_backstage_dialog(self, key))
            shortcut = BACKSTAGE_SHORTCUTS.get(entry.key)
            if shortcut:
                action.setShortcut(QtGui.QKeySequence(shortcut))
                self.addAction(action)

        notes_menu = bar.addMenu("笔记")
        notes_center_action = notes_menu.addAction("笔记中心…")
        notes_center_action.triggered.connect(lambda: open_notes_center_dialog(self))
        notes_center_action.setShortcut(QtGui.QKeySequence(NOTES_CENTER_SHORTCUT))
        self.addAction(notes_center_action)

        backtest_menu = bar.addMenu("回测")
        for entry in BACKTEST_ENTRIES:
            action = backtest_menu.addAction(f"{entry.label}…")
            action.triggered.connect(lambda _checked=False, key=entry.key: open_backtest_menu_dialog(self, key))
            shortcut = BACKTEST_SHORTCUTS.get(entry.key)
            if shortcut:
                action.setShortcut(QtGui.QKeySequence(shortcut))
                self.addAction(action)

        tools_menu = bar.addMenu("工具")
        self._ai_toggle_action = tools_menu.addAction("显示/隐藏 AI 悬浮球")
        self._ai_toggle_action.triggered.connect(self._toggle_floating_orb)
        ai_tools_action = tools_menu.addAction("AI 工具能力…")
        ai_tools_action.triggered.connect(lambda: open_ai_tools_dialog(self))
        audit_action = tools_menu.addAction("AI 工具审计…")
        audit_action.triggered.connect(lambda: open_ai_tool_audit_dialog(self))

        help_menu = bar.addMenu("帮助")
        shortcuts_action = help_menu.addAction("键盘快捷键…")
        shortcuts_action.triggered.connect(self._show_shortcuts_help)

        theme_menu = bar.addMenu("主题")
        theme_group = QtGui.QActionGroup(self)
        theme_group.setExclusive(True)
        self._theme_dark_action = theme_menu.addAction("深色")
        self._theme_dark_action.setCheckable(True)
        self._theme_dark_action.setData("dark")
        theme_group.addAction(self._theme_dark_action)
        self._theme_light_action = theme_menu.addAction("浅色")
        self._theme_light_action.setCheckable(True)
        self._theme_light_action.setData("light")
        theme_group.addAction(self._theme_light_action)
        self._theme_system_action = theme_menu.addAction("跟随系统")
        self._theme_system_action.setCheckable(True)
        self._theme_system_action.setData("system")
        theme_group.addAction(self._theme_system_action)
        self._sync_theme_menu_checks()
        theme_group.triggered.connect(self._on_theme_menu_triggered)

    def _sync_theme_menu_checks(self) -> None:
        current = self._theme_manager.current()
        if self._theme_dark_action is not None:
            self._theme_dark_action.setChecked(current == "dark")
        if self._theme_light_action is not None:
            self._theme_light_action.setChecked(current == "light")
        if self._theme_system_action is not None:
            self._theme_system_action.setChecked(current == "system")

    def _on_theme_menu_triggered(self, action: QtGui.QAction) -> None:
        theme_id = action.data()
        if theme_id not in ("dark", "light", "system"):
            return
        self._theme_manager.set_theme(theme_id)
        self._sync_theme_menu_checks()

    def edit_global_setting(self) -> None:
        show_settings_dialog(self)

    def _init_shell(self) -> None:
        self.sidebar = SidebarNav(APP_NAV_GROUPS, self)
        self.sidebar.page_changed.connect(self._on_nav_changed)

        self.stack = QtWidgets.QStackedWidget()
        self.stack.setObjectName("MainStack")

        self._nav_splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        self._nav_splitter.setObjectName("MainNavSplitter")
        self._nav_splitter.setHandleWidth(6)
        self._nav_splitter.setChildrenCollapsible(False)
        self._nav_splitter.addWidget(self.sidebar)
        self._nav_splitter.addWidget(self.stack)
        self._nav_splitter.setStretchFactor(0, 0)
        self._nav_splitter.setStretchFactor(1, 1)
        nav_width = self._load_nav_width()
        self._nav_splitter.setSizes([nav_width, max(640, self.width() - nav_width)])
        self._nav_splitter.splitterMoved.connect(self._on_nav_splitter_moved)

        body = QtWidgets.QHBoxLayout()
        body.setSpacing(0)
        body.setContentsMargins(0, 0, 0, 0)
        body.addWidget(self._nav_splitter, stretch=1)

        shell = QtWidgets.QWidget()
        shell.setLayout(body)

        self._theme_manager.bind_stylesheet(shell)
        self._theme_manager.bind_stylesheet(self.sidebar)
        self._theme_manager.bind_stylesheet(self.stack)
        self._theme_manager.bind_stylesheet(self)
        self._theme_manager.register_callback(self.sidebar.refresh_theme)
        self._theme_manager.apply()

        self.setCentralWidget(shell)
        self._toast = PageToastHost(self)
        self.setStatusBar(self._toast)
        bind_scheduler_notifications(self)
        self.sidebar.set_active_index(0)

    def schedule_initial_page(self) -> None:
        if self._initial_page_scheduled:
            return
        self._initial_page_scheduled = True
        QtCore.QTimer.singleShot(0, self._load_initial_page)

    def showEvent(self, event: QtGui.QShowEvent) -> None:
        super().showEvent(event)
        if not self._initial_page_scheduled and self._current_key is None:
            self.schedule_initial_page()

    def _load_initial_page(self) -> None:
        with profiler.phase("main_window_first_page"):
            self._show_page(0)
        schedule_deferred_shell_extras(self)
        schedule_deferred_watchlist_prewarm(self)
        schedule_deferred_radar_prewarm(self)
        schedule_deferred_scheduler_start(self)

    def _show_shortcuts_help(self) -> None:
        show_info_dialog(self, "键盘快捷键", format_shortcuts_help(), monospace=True)

    def _bind_nav_shortcuts(self) -> None:
        bind_main_window_shortcuts(
            self,
            show_page=self._show_page,
            focus_quotes_search=self._focus_quotes_search,
            toggle_floating_orb=self._toggle_floating_orb,
        )

    def _focus_quotes_search(self) -> None:
        key = self._current_key
        if key not in QUOTES_WIDGETS:
            return
        widget = self._page_widgets.get(key)
        if widget is None or not hasattr(widget, "page"):
            return
        search = getattr(widget.page, "search_edit", None)
        if search is None:
            return
        search.setFocus(QtCore.Qt.FocusReason.ShortcutFocusReason)
        search.selectAll()

    _NAV_WIDTH_KEY = "shell/nav_width"

    def _load_nav_width(self) -> int:
        value = read_setting_value(self._NAV_WIDTH_KEY, SidebarNav.DEFAULT_WIDTH)
        if isinstance(value, bool):
            width = SidebarNav.DEFAULT_WIDTH
        elif isinstance(value, (int, float)):
            width = int(value)
        elif isinstance(value, str):
            try:
                width = int(value)
            except ValueError:
                width = SidebarNav.DEFAULT_WIDTH
        else:
            width = SidebarNav.DEFAULT_WIDTH
        return int(max(SidebarNav.MIN_WIDTH, min(SidebarNav.MAX_WIDTH, width)))

    def _on_nav_splitter_moved(self, _pos: int, _index: int) -> None:
        sizes = self._nav_splitter.sizes()
        if not sizes:
            return
        nav_width = max(SidebarNav.MIN_WIDTH, min(SidebarNav.MAX_WIDTH, sizes[0]))
        if nav_width != sizes[0]:
            total = max(sum(sizes), nav_width + sizes[1])
            self._nav_splitter.blockSignals(True)
            self._nav_splitter.setSizes([nav_width, total - nav_width])
            self._nav_splitter.blockSignals(False)
        write_setting_value(self._NAV_WIDTH_KEY, nav_width)
        if self._floating_controller is not None:
            self._floating_controller.on_window_resize()

    def _get_llm_engine(self) -> LlmEngine | None:
        return get_llm_engine(self.main_engine)

    def _init_floating_ai(self, shell: QtWidgets.QWidget | None = None) -> bool:
        if self._floating_controller is not None:
            return True
        llm_engine = self._get_llm_engine()
        if llm_engine is None:
            return False
        if shell is None:
            shell = self.centralWidget()
        if shell is None:
            return False
        controller = FloatingAiController(self, llm_engine)
        controller.bind_page_key(lambda: self._current_key)
        if not controller.init(shell):
            return False
        self._floating_controller = controller
        return True

    def _ensure_floating_ai(self) -> bool:
        if self._init_floating_ai():
            return True
        page_notify(self, AI_NOT_LOADED_MSG, level="warning")
        return False

    def _toggle_floating_orb(self) -> None:
        if not self._ensure_floating_ai():
            return
        assert self._floating_controller is not None
        self._floating_controller.toggle_orb()

    def _return_to_floating_mode(self) -> None:
        if self._floating_controller is not None:
            self._floating_controller.return_from_fullscreen()

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:
        super().resizeEvent(event)
        if self._floating_controller is not None:
            self._floating_controller.on_window_resize()

    def _open_ai_page(self) -> None:
        open_ai_page(self)

    def _open_ai_tools_dialog(self) -> None:
        open_ai_tools_dialog(self)

    def register_floating_overlay(self, parent: QtWidgets.QWidget) -> None:
        if self._ensure_floating_ai() and self._floating_controller is not None:
            self._floating_controller.push_overlay_parent(parent)

    def unregister_floating_overlay(self, parent: QtWidgets.QWidget) -> None:
        if self._floating_controller is not None:
            self._floating_controller.pop_overlay_parent(parent)

    def on_floating_overlay_resized(self, parent: QtWidgets.QWidget) -> None:
        if self._floating_controller is not None:
            self._floating_controller.on_overlay_parent_resized(parent)

    def _nav_index_for_key(self, key: str) -> int | None:
        return nav_index_for_key(self, key)

    def _on_nav_changed(self, index: int) -> None:
        entry = self.sidebar.entry_at(index)
        if entry.key == "ai_assistant" and self._get_llm_engine() is None:
            page_notify(self, AI_NOT_LOADED_MSG, level="warning")
            if self._current_key:
                prev = self._nav_index_for_key(self._current_key)
                if prev is not None:
                    self.sidebar.set_active_index(prev)
            return
        self._show_page(index)

    def _show_page(self, index: int) -> None:
        entry = self.sidebar.entry_at(index)
        show_page_by_key(self, entry.key, nav_index=index)

    def open_screener_run(self, run_id: str, *, page_key: str) -> None:
        open_screener_run(self, run_id, page_key=page_key)

    def open_screener_industry(self, industry: str) -> None:
        open_screener_industry(self, industry)

    def open_screener_radar_resonance(self) -> None:
        open_screener_radar_resonance(self)

    def open_screener_leader_screen(self, *, variant: str = "mainline") -> None:
        open_screener_leader_screen(self, variant=variant)

    def open_sector_flow(
        self,
        sector_ids: list[str] | None = None,
        *,
        tab: str = "default",
        sector_kind: str | None = None,
    ) -> None:
        open_sector_flow(self, sector_ids, tab=tab, sector_kind=sector_kind)

    def open_market_industry_filter(self, industry: str) -> None:
        open_market_industry_filter(self, industry)

    def open_market_concept_drilldown(self, concept_name: str, vt_symbols: list[str]) -> None:
        open_market_concept_drilldown(self, concept_name, vt_symbols)

    def open_radar_card(self, card_id: str, *, variant: str | None = None, refresh: bool = True) -> None:
        open_radar_card(self, card_id, variant=variant, refresh=refresh)

    def open_radar_leader_loop(self, *, run_leader_screen: bool = False, leader_variant: str = "mainline") -> None:
        open_radar_leader_loop(self, run_leader_screen=run_leader_screen, leader_variant=leader_variant)

    def _show_page_by_key(self, key: str, *, nav_index: int | None = None) -> None:
        show_page_by_key(self, key, nav_index=nav_index)

    def _open_backstage_dialog(self, key: str) -> None:
        open_backstage_dialog(self, key)

    def _open_scheduler_dialog(self) -> None:
        open_scheduler_dialog(self)

    def navigate_to_page(self, key: str) -> None:
        navigate_to_page(self, key)

    def _open_local_data_dialog(self) -> None:
        open_local_data_dialog(self)

    def _open_data_manager_dialog(self) -> None:
        open_data_manager_dialog(self)

    def _open_notes_center_dialog(self) -> None:
        open_notes_center_dialog(self)

    def focus_watchlist_symbol(self, symbol: str, exchange_name: str) -> None:
        focus_watchlist_symbol(self, symbol, exchange_name)

    def _ensure_cta_backtester_app(self) -> None:
        ensure_cta_backtester_app(self.main_engine)

    def _ensure_data_manager_app(self) -> None:
        ensure_data_manager_app(self.main_engine)

    def _get_or_create_page(self, key: str) -> QtWidgets.QWidget | None:
        return get_or_create_page(self, key)

    def _open_scheduler_page(self) -> None:
        open_scheduler_dialog(self)

    def _refresh_info_feed_badge(self) -> None:
        refresh_info_feed_badge(self)

    def _bind_scheduler_notifications(self) -> None:
        bind_scheduler_notifications(self)

    def _on_scheduler_job_event(self, job_id: str) -> None:
        on_scheduler_job_event(self, job_id)

    def _handle_scheduler_job(self, job_id: str) -> None:
        handle_scheduler_job(self, job_id)

    def open_widget(self, widget_class: type[QtWidgets.QWidget], name: str) -> None:
        if try_open_vnpy_widget(self, widget_class, name):
            return
        super().open_widget(widget_class, name)

    def load_window_setting(self, name: str) -> None:
        key = f"shell/geometry/{name}"
        geometry = read_setting_value(key, None)
        restore_geometry_on_screen(self, geometry)

    def save_window_setting(self, name: str) -> None:
        write_setting_value(f"shell/geometry/{name}", self.saveGeometry())

    def closeEvent(self, event) -> None:
        if self._floating_controller is not None:
            self._floating_controller.deactivate()
        for widget in self._page_widgets.values():
            if hasattr(widget, "deactivate"):
                widget.deactivate()
        super().closeEvent(event)
