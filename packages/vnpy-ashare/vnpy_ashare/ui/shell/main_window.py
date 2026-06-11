"""A 股终端主窗口：左侧菜单切换 市场 / 自选 / 本地 等功能页。"""

from __future__ import annotations

from importlib import import_module
from types import ModuleType

from vnpy.event import Event, EventEngine
from vnpy.trader.engine import MainEngine
from vnpy.trader.ui import MainWindow
from vnpy.trader.ui.qt import QtCore, QtGui, QtWidgets

from vnpy_ashare.ai.ui import AiPageWidget
from vnpy_ashare.app.branding import window_title as build_window_title
from vnpy_ashare.app.engine import APP_NAME, AshareEngine
from vnpy_ashare.app.events import (
    EVENT_AI_ACTION,
    EVENT_ASK_AI,
    EVENT_FILL_SCREENER,
    EVENT_OPEN_BACKTEST,
    EVENT_OPEN_BATCH_BACKTEST,
    EVENT_ORB_ATTENTION,
    AiActionRequest,
    AskAiRequest,
    BacktestRequest,
    BatchBacktestViewRequest,
    FillScreenerRequest,
    OrbAttentionRequest,
)
from vnpy_ashare.domain.ai_actions import (
    AI_ACTION_ASK_AI,
    AI_ACTION_FILL_RECIPE,
    AI_ACTION_FILL_SCREENER,
    AI_ACTION_OPEN_BACKTEST,
    AI_ACTION_OPEN_BATCH_BACKTEST,
    AI_ACTION_ORB_ATTENTION,
    normalize_ai_action,
)
from vnpy_ashare.ui.backtest import BatchBacktestPageWidget
from vnpy_ashare.ui.scheduler.scheduler_page import SchedulerPageWidget
from vnpy_ashare.ui.screener import (
    AutoScreenerPageWidget,
    ScreenerPageWidget,
    show_recipe_confirm_dialog,
    show_screener_confirm_dialog,
)
from vnpy_ashare.ui.shell.floating_controller import FloatingAiController
from vnpy_ashare.ui.shell.nav import (
    APP_NAV_ENTRIES,
    APP_NAV_GROUPS,
    BACKSTAGE_ENTRIES,
    BACKSTAGE_PAGE_KEYS,
    BACKSTAGE_SHORTCUTS,
    NAV_SHORTCUTS,
    SidebarNav,
)
from vnpy_ashare.ui.shell.page_shell import LocalPageWidget, MarketPageWidget, RadarPageWidget, WatchlistPageWidget
from vnpy_ashare.ui.shell.settings.dialog import show_settings_dialog
from vnpy_common.paths import QSETTINGS_ORG
from vnpy_common.ui.feedback import PageToastHost, page_notify, show_info_dialog
from vnpy_common.ui.qt_helpers import restore_geometry_on_screen
from vnpy_common.ui.theme import theme_manager
from vnpy_llm.app.engine import APP_NAME as LLM_APP_NAME
from vnpy_llm.app.engine import LlmEngine
from vnpy_llm.ui.dialogs.tool_audit import show_ai_tool_audit_dialog
from vnpy_llm.ui.dialogs.tools import show_ai_tools_dialog

_QUOTES_WIDGETS: dict[str, type[QtWidgets.QWidget]] = {
    "market": MarketPageWidget,
    "radar": RadarPageWidget,
    "watchlist": WatchlistPageWidget,
    "local": LocalPageWidget,
}

_DEFERRED_PAGE_KEYS = frozenset({"cta_backtest", "data_manager", "batch_backtest"})

_AI_NOT_LOADED_MSG = "AI 助手未加载，请确认已安装并启用 vnpy_llm"

_VNPY_WIDGETS: dict[str, tuple[str, str]] = {
    "cta_backtest": ("vnpy_ashare.ui.backtest.pages.backtest_widget", "BacktesterWidget"),
    "data_manager": ("vnpy_ashare.ui.shell.manager.widget", "ManagerWidget"),
}


class AshareMainWindow(MainWindow):
    """左侧图标菜单 + 中央内容区，不再使用顶部「功能」「微信」「帮助」菜单。"""

    # EventEngine 在后台线程回调，须经 Signal 切回 GUI 线程再操作控件。
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
        self._screener_draft_connected = False
        self._scheduler_listener_connected = False
        self._deferred_apps_registered = False
        self._theme_manager = theme_manager()
        self._theme_dark_action: QtGui.QAction | None = None
        self._theme_light_action: QtGui.QAction | None = None
        self._theme_system_action: QtGui.QAction | None = None
        super().__init__(main_engine, event_engine)
        self._signal_open_backtest.connect(self._handle_open_backtest)
        self._signal_open_batch_backtest.connect(self._handle_open_batch_backtest)
        self._signal_fill_screener.connect(self._handle_fill_screener)
        self._signal_ask_ai.connect(self._handle_ask_ai)
        self._signal_orb_attention.connect(self._handle_orb_attention)
        self._signal_ai_action.connect(self._handle_ai_action)
        self._signal_scheduler_job.connect(self._handle_scheduler_job)
        self.event_engine.register(EVENT_OPEN_BACKTEST, self._on_open_backtest_event)
        self.event_engine.register(EVENT_OPEN_BATCH_BACKTEST, self._on_open_batch_backtest_event)
        self.event_engine.register(EVENT_FILL_SCREENER, self._on_fill_screener_event)
        self.event_engine.register(EVENT_ASK_AI, self._on_ask_ai_event)
        self.event_engine.register(EVENT_ORB_ATTENTION, self._on_orb_attention_event)
        self.event_engine.register(EVENT_AI_ACTION, self._on_ai_action_event)

    def init_dock(self) -> None:
        """不使用 vnpy 默认 Dock（交易/日志面板）。"""

    def init_toolbar(self) -> None:
        self.toolbar = QtWidgets.QToolBar(self)
        self.toolbar.setVisible(False)

    def init_ui(self) -> None:
        self.window_title = build_window_title()
        self.setWindowTitle(self.window_title)
        self.init_dock()
        self.init_toolbar()
        self._theme_manager.load_saved()
        self.init_menu()
        self._init_shell()
        self._bind_nav_shortcuts()
        self.load_window_setting("custom")

    def init_menu(self) -> None:
        super().init_menu()
        bar = self.menuBar()
        _HIDDEN_MENU_LABELS = frozenset(
            {
                "功能",
                "Func",
                "微信",
                "WeChat",
                "帮助",
                "Help",
            }
        )
        for action in bar.actions():
            text = action.text().replace("&", "")
            if text in _HIDDEN_MENU_LABELS:
                bar.removeAction(action)

        backstage_menu = bar.addMenu("后台")
        for entry in BACKSTAGE_ENTRIES:
            action = backstage_menu.addAction(f"{entry.label}…")
            action.triggered.connect(lambda _checked=False, key=entry.key: self._show_page_by_key(key))
            shortcut = BACKSTAGE_SHORTCUTS.get(entry.key)
            if shortcut:
                action.setShortcut(QtGui.QKeySequence(shortcut))
                self.addAction(action)

        tools_menu = bar.addMenu("工具")
        self._ai_toggle_action = tools_menu.addAction("显示/隐藏 AI 悬浮球")
        self._ai_toggle_action.setShortcuts(
            [
                QtGui.QKeySequence("Ctrl+L"),
                QtGui.QKeySequence("Meta+L"),
            ]
        )
        self._ai_toggle_action.triggered.connect(self._toggle_floating_orb)
        self.addAction(self._ai_toggle_action)
        tools_menu.addSeparator()
        ai_tools_action = tools_menu.addAction("AI 工具能力…")
        ai_tools_action.triggered.connect(self._open_ai_tools_dialog)
        audit_action = tools_menu.addAction("AI 工具审计…")
        audit_action.triggered.connect(self._open_ai_tool_audit_dialog)

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
        if self._init_floating_ai(shell):
            assert self._floating_controller is not None
            self._floating_controller.bind_content_anchor(self.stack)
        self._bind_scheduler_notifications()
        self._schedule_deferred_scheduler_start()
        self._show_page(0)

    def _show_shortcuts_help(self) -> None:
        lines = [
            "页面切换",
            *(f"  {NAV_SHORTCUTS.get(entry.key, '—'):8}  {entry.label}" for entry in APP_NAV_ENTRIES),
            "",
            "后台",
            *(
                f"  {BACKSTAGE_SHORTCUTS.get(entry.key, '—'):8}  {entry.label}"
                for entry in BACKSTAGE_ENTRIES
            ),
            "",
            "全局",
            "  Ctrl+F    聚焦当前页搜索框",
            "  Ctrl+L    显示/隐藏 AI 悬浮球",
        ]
        show_info_dialog(self, "键盘快捷键", "\n".join(lines), monospace=True)

    def _bind_nav_shortcuts(self) -> None:
        """Ctrl+1~9 切换侧栏页面；Ctrl+F 聚焦行情搜索。"""
        for index, entry in enumerate(APP_NAV_ENTRIES):
            shortcut = NAV_SHORTCUTS.get(entry.key)
            if not shortcut:
                continue
            action = QtGui.QAction(f"打开{entry.label}", self)
            action.setShortcut(QtGui.QKeySequence(shortcut))
            action.triggered.connect(lambda _checked=False, i=index: self._show_page(i))
            self.addAction(action)

        focus_search = QtGui.QAction("聚焦搜索", self)
        focus_search.setShortcut(QtGui.QKeySequence("Ctrl+F"))
        focus_search.triggered.connect(self._focus_quotes_search)
        self.addAction(focus_search)

    def _focus_quotes_search(self) -> None:
        key = self._current_key
        if key not in _QUOTES_WIDGETS:
            return
        widget = self._page_widgets.get(key)
        if widget is None or not hasattr(widget, "page"):
            return
        search = getattr(widget.page, "search_edit", None)
        if search is None:
            return
        search.setFocus(QtCore.Qt.FocusReason.ShortcutFocusReason)
        search.selectAll()

    def _schedule_deferred_scheduler_start(self) -> None:
        """冷启动：窗口就绪后再启动 APScheduler。"""
        QtCore.QTimer.singleShot(2000, self._deferred_scheduler_start)

    def _deferred_scheduler_start(self) -> None:
        engine = self.main_engine.get_engine(APP_NAME)
        if isinstance(engine, AshareEngine):
            engine.scheduler.ensure_started()

    def _nav_width_settings(self) -> QtCore.QSettings:
        return QtCore.QSettings(QSETTINGS_ORG, "ashare_ui")

    def _load_nav_width(self) -> int:
        value = self._nav_width_settings().value("nav_width", SidebarNav.DEFAULT_WIDTH)
        try:
            width = int(value)
        except (TypeError, ValueError):
            width = SidebarNav.DEFAULT_WIDTH
        return max(SidebarNav.MIN_WIDTH, min(SidebarNav.MAX_WIDTH, width))

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
        self._nav_width_settings().setValue("nav_width", nav_width)
        if self._floating_controller is not None:
            self._floating_controller.on_window_resize()

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
        engine.signals.recipe_draft_ready.connect(self._on_recipe_draft_ready)
        self._screener_draft_connected = True

    def _on_screener_draft_ready(self, draft_id: str) -> None:
        engine = self.main_engine.get_engine(LLM_APP_NAME)
        if not isinstance(engine, LlmEngine):
            return
        show_screener_confirm_dialog(draft_id, engine, parent=self)

    def _on_recipe_draft_ready(self, draft_id: str) -> None:
        engine = self.main_engine.get_engine(LLM_APP_NAME)
        if not isinstance(engine, LlmEngine):
            return
        show_recipe_confirm_dialog(draft_id, engine, parent=self)

    def _open_ai_tools_dialog(self) -> None:
        llm_engine = self._get_llm_engine()
        if llm_engine is None:
            page_notify(self, _AI_NOT_LOADED_MSG, level="warning")
            return
        show_ai_tools_dialog(llm_engine, self)

    def _open_ai_tool_audit_dialog(self) -> None:
        llm_engine = self._get_llm_engine()
        if llm_engine is None:
            page_notify(self, _AI_NOT_LOADED_MSG, level="warning")
            return
        show_ai_tool_audit_dialog(llm_engine, self)

    def _init_floating_ai(self, shell: QtWidgets.QWidget | None = None) -> bool:
        """创建悬浮球协调层。"""
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
        page_notify(self, _AI_NOT_LOADED_MSG, level="warning")
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
        llm_engine = self._get_llm_engine()
        if llm_engine is None:
            page_notify(self, _AI_NOT_LOADED_MSG, level="warning")
            return
        llm_engine.open_session_for_ask(surface="assistant")
        index = self._nav_index_for_key("ai_assistant")
        if index is None:
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

    def _handle_fill_recipe(self, data) -> None:
        index = self._nav_index_for_key("auto_screener")
        if index is None:
            return
        self._show_page(index)
        widget = self._page_widgets.get("auto_screener")
        if widget is not None and hasattr(widget, "apply_recipe_request"):
            widget.apply_recipe_request(data)

    def _on_ask_ai_event(self, event: Event) -> None:
        if isinstance(event.data, AskAiRequest):
            self._signal_ask_ai.emit(event.data)

    def _on_orb_attention_event(self, event: Event) -> None:
        if isinstance(event.data, OrbAttentionRequest):
            self._signal_orb_attention.emit(event.data)

    def _on_ai_action_event(self, event: Event) -> None:
        if isinstance(event.data, AiActionRequest):
            self._signal_ai_action.emit(event.data)

    def _handle_ai_action(self, data: AiActionRequest) -> None:
        try:
            action = normalize_ai_action(data)
        except (TypeError, ValueError):
            return
        payload = action.payload
        if action.kind == AI_ACTION_FILL_SCREENER:
            assert isinstance(payload, FillScreenerRequest)
            self._handle_fill_screener(payload)
        elif action.kind == AI_ACTION_FILL_RECIPE:
            from vnpy_ashare.app.events import FillRecipeRequest

            assert isinstance(payload, FillRecipeRequest)
            self._handle_fill_recipe(payload)
        elif action.kind == AI_ACTION_ASK_AI:
            assert isinstance(payload, AskAiRequest)
            self._handle_ask_ai(payload)
        elif action.kind == AI_ACTION_OPEN_BACKTEST:
            assert isinstance(payload, BacktestRequest)
            self._handle_open_backtest(payload)
        elif action.kind == AI_ACTION_OPEN_BATCH_BACKTEST:
            assert isinstance(payload, BatchBacktestViewRequest)
            self._handle_open_batch_backtest(payload)
        elif action.kind == AI_ACTION_ORB_ATTENTION:
            assert isinstance(payload, OrbAttentionRequest)
            self._handle_orb_attention(payload)

    def _handle_orb_attention(self, data: OrbAttentionRequest) -> None:
        if not self._ensure_floating_ai():
            return
        if self._floating_controller is not None:
            self._floating_controller.notify_attention(data.source)

    def _handle_ask_ai(self, data: AskAiRequest) -> None:
        if data.use_full_page:
            llm_engine = self._get_llm_engine()
            if llm_engine is None:
                page_notify(self, _AI_NOT_LOADED_MSG, level="warning")
                return
            llm_engine.open_session_for_ask(
                surface="assistant",
                new_session=data.new_session,
                session_policy=data.session_policy,
                scene=data.scene or data.source_page,
            )
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
        if self._floating_controller is not None:
            self._floating_controller.handle_ask_ai(data)

    def _nav_index_for_key(self, key: str) -> int | None:
        for index, entry in enumerate(APP_NAV_ENTRIES):
            if entry.key == key:
                return index
        return None

    def _on_nav_changed(self, index: int) -> None:
        entry = self.sidebar.entry_at(index)
        if entry.key == "ai_assistant" and self._get_llm_engine() is None:
            page_notify(self, _AI_NOT_LOADED_MSG, level="warning")
            if self._current_key:
                prev = self._nav_index_for_key(self._current_key)
                if prev is not None:
                    self.sidebar.set_active_index(prev)
            return
        self._show_page(index)

    def _show_page(self, index: int) -> None:
        entry = self.sidebar.entry_at(index)
        self._show_page_by_key(entry.key, nav_index=index)

    def _show_page_by_key(self, key: str, *, nav_index: int | None = None) -> None:
        widget = self._get_or_create_page(key)
        if widget is None:
            return

        if key == "ai_assistant":
            if self._current_key and self._current_key != "ai_assistant":
                prev_index = self._nav_index_for_key(self._current_key)
                if prev_index is not None:
                    self._page_before_ai = prev_index
            if self._floating_controller is not None:
                self._floating_controller.on_ai_assistant_entered()

        if self._current_key and self._current_key != key:
            old = self._page_widgets.get(self._current_key)
            if old is not None and hasattr(old, "deactivate"):
                old.deactivate()

        if self.stack.indexOf(widget) < 0:
            self.stack.addWidget(widget)
        self.stack.setCurrentWidget(widget)

        if hasattr(widget, "activate"):
            widget.activate()

        self._current_key = key
        if key != "ai_assistant" and nav_index is not None:
            self._page_before_ai = nav_index
        if self._floating_controller is not None:
            self._floating_controller.on_page_changed(key)
            self._floating_controller.raise_floating_layers()
        if nav_index is not None:
            self.sidebar.set_active_index(nav_index)
        elif key in BACKSTAGE_PAGE_KEYS:
            self.sidebar.clear_active()
        self.raise_()
        self.activateWindow()

    def _ensure_deferred_apps(self) -> None:
        if self._deferred_apps_registered:
            return
        from vnpy_ashare.app.launcher import _register_deferred_apps

        _register_deferred_apps(self.main_engine)
        self._deferred_apps_registered = True

    def _get_or_create_page(self, key: str) -> QtWidgets.QWidget | None:
        if key in _DEFERRED_PAGE_KEYS:
            self._ensure_deferred_apps()
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
        elif key == "auto_screener":
            widget = AutoScreenerPageWidget(self.main_engine, self.event_engine)
            widget.open_scheduler_requested.connect(self._open_scheduler_page)
        elif key == "batch_backtest":
            widget = BatchBacktestPageWidget(self.main_engine, self.event_engine)
        elif key == "scheduler":
            widget = SchedulerPageWidget(self.main_engine, self.event_engine)

        if widget is not None:
            self._page_widgets[key] = widget
            self.widgets[key] = widget
            extra = ""
            if key == "scheduler":
                from vnpy_common.ui.theme.build_extra import build_scheduler_page_stylesheet

                extra = build_scheduler_page_stylesheet
            self._theme_manager.bind_stylesheet(widget, extra=extra)

        return widget

    def _open_scheduler_page(self) -> None:
        self._show_page_by_key("scheduler")

    def _bind_scheduler_notifications(self) -> None:
        if self._scheduler_listener_connected:
            return
        engine = self.main_engine.get_engine(APP_NAME)
        if not isinstance(engine, AshareEngine):
            return
        engine.scheduler.add_listener(self._on_scheduler_job_event)
        self._scheduler_listener_connected = True

    def _on_scheduler_job_event(self, job_id: str) -> None:
        self._signal_scheduler_job.emit(job_id)

    def _handle_scheduler_job(self, job_id: str) -> None:
        if job_id not in ("screen_intraday", "screen_post_close"):
            return
        engine = self.main_engine.get_engine(APP_NAME)
        if not isinstance(engine, AshareEngine):
            return
        status = engine.scheduler.get_status(job_id)
        if status is None or status.last_success is not True:
            return
        message = status.last_message or "自动选股已完成"
        if message and "跳过" in message:
            return
        widget = self._page_widgets.get("auto_screener")
        if widget is not None and hasattr(widget, "on_scheduled_run_complete"):
            widget.on_scheduled_run_complete(job_id, message)
        if self._current_key != "auto_screener":
            self.event_engine.put(
                Event(EVENT_ORB_ATTENTION, OrbAttentionRequest(source="auto_screener")),
            )

    def open_widget(self, widget_class: type[QtWidgets.QWidget], name: str) -> None:
        name_map = {
            "Ashare": "watchlist",
            "CtaBacktester": "cta_backtest",
            "DataManager": "data_manager",
        }
        key = name_map.get(name)
        if key:
            nav_index = self._nav_index_for_key(key)
            if nav_index is not None:
                self._show_page(nav_index)
            else:
                self._show_page_by_key(key)
            return
        super().open_widget(widget_class, name)

    def load_window_setting(self, name: str) -> None:
        settings = QtCore.QSettings(self.window_title, name)
        restore_geometry_on_screen(self, settings.value("geometry"))

    def save_window_setting(self, name: str) -> None:
        settings = QtCore.QSettings(self.window_title, name)
        settings.setValue("geometry", self.saveGeometry())

    def closeEvent(self, event) -> None:
        if self._floating_controller is not None:
            self._floating_controller.deactivate()
        for widget in self._page_widgets.values():
            if hasattr(widget, "deactivate"):
                widget.deactivate()
        super().closeEvent(event)
