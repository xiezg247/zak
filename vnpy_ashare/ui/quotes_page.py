"""行情列表页：市场 / 自选 / 本地 各自独立。"""

from __future__ import annotations

from typing import Literal

from vnpy.event import EventEngine

from vnpy.trader.constant import Exchange, Interval
from vnpy.trader.ui import QtCore, QtGui, QtWidgets

from vnpy_ashare.bar_health import (
    BarGapResult,
    BarHealthStatus,
    BarMeta,
    format_meta_date,
)
from vnpy_ashare.bars import cleanup_invalid_daily_bars
from vnpy_ashare.minute_periods import LOCAL_SCOPE_OPTIONS
from vnpy_ashare.calendar import last_trading_day
from vnpy_ashare.config import format_vt_symbol_cn
from vnpy_ashare.quotes import QuoteSnapshot
from vnpy_ashare.quotes.depth_snapshot import DepthSnapshot
from vnpy_ashare.ui.styles import apply_toolbar_combo_style
from vnpy_ashare.ui.quotes.actions_controller import ActionsController
from vnpy_ashare.ui.quotes.local_data_controller import LocalDataController, should_apply_loaded_bars
from vnpy_ashare.ui.quotes.pagination_controller import MarketPaginationController
from vnpy_ashare.ui.quotes.quote_stream_controller import QuoteStreamController
from vnpy_ashare.ui.quotes.table_controller import TableController
from vnpy_ashare.ui.quotes.watchlist_controller import WatchlistController
from vnpy_ashare.ui.quotes.workers import (
    BarGapCheckWorker,
    BarsLoadWorker,
    DepthRefreshWorker,
    DiagnoseWorker,
    DownloadWorker,
    MarketPageLoadWorker,
    MarketPageResult,
    MinuteDownloadWorker,
    QuotesRefreshWorker,
    UniverseLoadWorker,
    UniverseSyncWorker,
)
from vnpy_ashare.app_db import universe_exists
from vnpy_ashare.models import StockItem
from vnpy_ashare.quotes.tickflow_stream import TickflowStreamBridge
from vnpy_ashare.ui.chart_panel import ChartPanel
from vnpy_ashare.ui.chart_style import CHART_FRAME_STYLESHEET
from vnpy_ashare.ui.depth_panel import DepthPanel
from vnpy_ashare.ui.ma_legend import MaLegendBar
from vnpy_ashare.ui.qt_helpers import release_thread
from vnpy_ashare.ui.quote_columns import (
    LOCAL_TABLE_HEADERS,
)
from vnpy_ashare.ui.quotes_chart import create_daily_chart
from vnpy_ashare.ui.diagnose_panel import DiagnosePanel
from vnpy_ashare.ui.quotes_config import (
    PAGE_CONFIGS,
    quote_refresh_hint,
    SEARCH_DEBOUNCE_MS,
    TABLE_HEADERS_LOCAL,
    TABLE_HEADERS_WITH_LOCAL,
)

class QuotesPage(QtWidgets.QWidget):
    """单页行情：列表 + 报价头 + 日 K。"""

    @staticmethod
    def _thread_active(worker: QtCore.QThread | None) -> bool:
        if worker is None:
            return False
        try:
            return worker.isRunning()
        except RuntimeError:
            return False

    def _wait_worker_release(self, attr: str, *, timeout_ms: int = 500) -> None:
        worker = getattr(self, attr, None)
        if worker is None:
            return
        setattr(self, attr, None)
        release_thread(self._retired_workers, worker, timeout_ms=timeout_ms)

    def __init__(
        self,
        page_name: str,
        parent: QtWidgets.QWidget | None = None,
        *,
        event_engine: EventEngine | None = None,
    ) -> None:
        super().__init__(parent)
        self.config = PAGE_CONFIGS[page_name]
        self.page_name = page_name
        self.event_engine = event_engine

        self.all_stocks: list[StockItem] = []
        self.display_stocks: list[StockItem] = []
        self.quote_map: dict[str, QuoteSnapshot] = {}
        self.downloaded_keys: set[tuple[str, Exchange]] = set()
        self.bar_meta: dict[tuple[str, Exchange], BarMeta] = {}
        self.bar_list_status: dict[tuple[str, Exchange], BarHealthStatus] = {}
        self._selected_gap_result: BarGapResult | None = None
        self.current_item: StockItem | None = None
        self._watchlist = WatchlistController(self)
        self._pagination = MarketPaginationController(self)
        self._stream = QuoteStreamController(self)
        self._local = LocalDataController(self)
        self._table = TableController(self)
        self._actions = ActionsController(self)
        self._retired_workers: list[QtCore.QThread] = []
        self._load_generation = 0
        self._bars_generation = 0
        self._bars_request_id = 0
        self._active = False
        self._market_page = 0
        self._market_total = 0
        self._market_board: str | None = None
        self._apply_default_table_sort = False

        self._load_worker: UniverseLoadWorker | None = None
        self._market_worker: MarketPageLoadWorker | None = None
        self._sync_worker: UniverseSyncWorker | None = None
        self._bars_worker: BarsLoadWorker | None = None
        self._download_worker: DownloadWorker | None = None
        self._gap_worker: BarGapCheckWorker | None = None
        self._gap_generation = 0
        self._quotes_worker: QuotesRefreshWorker | None = None
        self._depth_worker: DepthRefreshWorker | None = None
        self._diagnose_worker: DiagnoseWorker | None = None
        self._depth_generation = 0
        self._depth_permission_denied = False
        self.depth_panel: DepthPanel | None = None
        self.diagnose_panel: DiagnosePanel | None = None
        self.chart_panel: ChartPanel | None = None
        self.chart_hint: QtWidgets.QLabel | None = None
        self._stream_bridge: TickflowStreamBridge | None = None
        self._stream_fallback = False
        self._local_scope = "daily"
        self._splitter: QtWidgets.QSplitter | None = None
        self._column_menu: QtWidgets.QMenu | None = None
        self._stats_label: QtWidgets.QLabel | None = None
        self._open_label: QtWidgets.QLabel | None = None
        self._high_label: QtWidgets.QLabel | None = None
        self._low_label: QtWidgets.QLabel | None = None
        self._volume_label: QtWidgets.QLabel | None = None

        self._search_timer = QtCore.QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(SEARCH_DEBOUNCE_MS)
        self._search_timer.timeout.connect(self.apply_filter)

        self._quote_timer = QtCore.QTimer(self)
        self._quote_timer.setInterval(self.config.quote_refresh_ms)
        self._quote_timer.timeout.connect(self.refresh_quotes)

        self._init_ui()

    def _init_columns(self) -> None:
        self._table.init_columns()

    def _build_visible_headers(self) -> list[str]:
        return self._table.build_visible_headers()

    def _init_ui(self) -> None:
        self._init_columns()
        if self.config.use_local_table:
            headers = LOCAL_TABLE_HEADERS
        else:
            headers = self._build_visible_headers()

        self.search_edit = QtWidgets.QLineEdit()
        self.search_edit.setObjectName("SearchBox")
        self.search_edit.setPlaceholderText(self.config.search_placeholder)
        self.search_edit.textChanged.connect(lambda _: self._search_timer.start())

        self.board_combo = QtWidgets.QComboBox()
        self.board_combo.setObjectName("BoardCombo")
        self.board_combo.addItems(["全部", "沪深主板", "创业板", "科创板", "北交所"])
        self.board_combo.setVisible(self.config.show_board_filter)
        self.board_combo.currentIndexChanged.connect(self._on_board_changed)

        self.sync_button = QtWidgets.QPushButton("同步 A 股列表")
        self.sync_button.clicked.connect(self.sync_universe_clicked)
        self.sync_button.setVisible(self.config.show_sync_button)

        self.download_button = QtWidgets.QPushButton("下载日K到本地")
        self.download_button.clicked.connect(self.download_selected)
        self.download_button.setEnabled(False)
        self.download_button.setVisible(self.config.show_download_button)

        self.fill_button = QtWidgets.QPushButton("补全到最新")
        self.fill_button.clicked.connect(self.fill_selected)
        self.fill_button.setEnabled(False)
        self.fill_button.setVisible(self.config.show_fill_button)

        self.redownload_button = QtWidgets.QPushButton("重新下载")
        self.redownload_button.clicked.connect(self.redownload_selected)
        self.redownload_button.setEnabled(False)
        self.redownload_button.setVisible(self.config.show_redownload_button)

        self.local_period_combo = QtWidgets.QComboBox()
        for label, value in LOCAL_SCOPE_OPTIONS:
            self.local_period_combo.addItem(label, value)
        apply_toolbar_combo_style(self.local_period_combo)
        self.local_period_combo.setVisible(self.config.use_local_table)
        self.local_period_combo.currentIndexChanged.connect(self._on_local_period_changed)

        self.add_watchlist_button = QtWidgets.QPushButton("加入自选")
        self.add_watchlist_button.clicked.connect(self._watchlist.add_selected)
        self.add_watchlist_button.setEnabled(False)
        self.add_watchlist_button.setVisible(self.config.show_add_watchlist_button)

        self.remove_watchlist_button = QtWidgets.QPushButton("移出自选")
        self.remove_watchlist_button.clicked.connect(self._watchlist.remove_selected)
        self.remove_watchlist_button.setEnabled(False)
        self.remove_watchlist_button.setVisible(self.config.show_remove_watchlist_button)

        self.move_watchlist_up_button = QtWidgets.QPushButton("上移")
        self.move_watchlist_up_button.clicked.connect(
            lambda: self._watchlist.move_selected("up")
        )
        self.move_watchlist_up_button.setEnabled(False)
        self.move_watchlist_up_button.setVisible(self.config.show_watchlist_move_buttons)

        self.move_watchlist_down_button = QtWidgets.QPushButton("下移")
        self.move_watchlist_down_button.clicked.connect(
            lambda: self._watchlist.move_selected("down")
        )
        self.move_watchlist_down_button.setEnabled(False)
        self.move_watchlist_down_button.setVisible(self.config.show_watchlist_move_buttons)

        self.backtest_button = QtWidgets.QPushButton("策略回测")
        self.backtest_button.clicked.connect(self._actions.open_backtest_for_selected)
        self.backtest_button.setEnabled(False)
        self.backtest_button.setVisible(self.config.show_backtest_button)

        self.diagnose_button = QtWidgets.QPushButton("诊断")
        self.diagnose_button.clicked.connect(self._actions.run_diagnose_for_selected)
        self.diagnose_button.setEnabled(False)
        self.diagnose_button.setVisible(self.config.show_diagnose_button)

        self.refresh_quotes_button = QtWidgets.QPushButton("刷新行情")
        self.refresh_quotes_button.clicked.connect(self._refresh_market_clicked)
        self.refresh_quotes_button.setVisible(self.config.use_market_rank)

        toolbar = QtWidgets.QHBoxLayout()
        toolbar.addWidget(self.search_edit, stretch=1)
        if self.config.show_board_filter:
            toolbar.addWidget(self.board_combo)

        # ── 分隔线 ──
        group2_visible = self.config.use_market_rank or self.config.show_sync_button
        if group2_visible:
            sep1 = QtWidgets.QFrame()
            sep1.setObjectName("ToolbarSeparator")
            sep1.setFrameShape(QtWidgets.QFrame.Shape.VLine)
            toolbar.addWidget(sep1)

        if self.config.use_market_rank:
            toolbar.addWidget(self.refresh_quotes_button)
        if self.config.show_sync_button:
            toolbar.addWidget(self.sync_button)

        # ── 分隔线 ──
        group3_visible = (
            self.config.show_add_watchlist_button
            or self.config.show_download_button
            or self.config.show_backtest_button
        )
        if group2_visible and group3_visible:
            sep2 = QtWidgets.QFrame()
            sep2.setObjectName("ToolbarSeparator")
            sep2.setFrameShape(QtWidgets.QFrame.Shape.VLine)
            toolbar.addWidget(sep2)

        if self.config.use_local_table:
            toolbar.addWidget(self.local_period_combo)
        if self.config.show_add_watchlist_button:
            toolbar.addWidget(self.add_watchlist_button)
        if self.config.show_remove_watchlist_button:
            toolbar.addWidget(self.remove_watchlist_button)
        if self.config.show_watchlist_move_buttons:
            toolbar.addWidget(self.move_watchlist_up_button)
            toolbar.addWidget(self.move_watchlist_down_button)
        if self.config.show_download_button:
            toolbar.addWidget(self.download_button)
        if self.config.show_fill_button:
            toolbar.addWidget(self.fill_button)
        if self.config.show_redownload_button:
            toolbar.addWidget(self.redownload_button)
        if self.config.show_backtest_button:
            toolbar.addWidget(self.backtest_button)
        if self.config.show_diagnose_button:
            toolbar.addWidget(self.diagnose_button)
        if self.config.column_configurable:
            self.column_button = QtWidgets.QPushButton("列 ▾")
            self.column_button.setObjectName("ColumnButton")
            self.column_button.clicked.connect(self._table.show_column_menu)
            toolbar.addWidget(self.column_button)

        self.prev_page_button = QtWidgets.QPushButton("◀ 上一页")
        self.prev_page_button.clicked.connect(self._go_prev_page)
        self.next_page_button = QtWidgets.QPushButton("下一页 ▶")
        self.next_page_button.clicked.connect(self._go_next_page)
        self.page_label = QtWidgets.QLabel("")
        self.page_total_label = QtWidgets.QLabel("")

        self.home_button = QtWidgets.QPushButton("⏮ 首页")
        self.home_button.clicked.connect(self._go_home_page)
        self.end_button = QtWidgets.QPushButton("尾页 ⏭")
        self.end_button.clicked.connect(self._go_end_page)
        self.page_jump_input = QtWidgets.QLineEdit()
        self.page_jump_input.setObjectName("PageJumpInput")
        self.page_jump_input.setPlaceholderText("跳页")
        self.page_jump_input.setFixedWidth(52)
        self.page_jump_input.returnPressed.connect(self._page_jump)

        self.pagination_bar = QtWidgets.QHBoxLayout()
        self.pagination_bar.addWidget(self.home_button)
        self.pagination_bar.addWidget(self.prev_page_button)
        self.pagination_bar.addWidget(self.page_label)
        self.pagination_bar.addWidget(self.page_jump_input)
        self.pagination_bar.addWidget(self.page_total_label)
        self.pagination_bar.addWidget(self.next_page_button)
        self.pagination_bar.addWidget(self.end_button)
        self._set_pagination_visible(self.config.use_market_rank)

        self.stats_label = QtWidgets.QLabel("")
        self.stats_label.setObjectName("StatsLabel")
        self.stats_label.setStyleSheet(f"color: {NAV_MUTED_COLOR}; padding: 2px 6px;")
        self.stats_label.setVisible(self.config.column_configurable)

        self.market_table = QtWidgets.QTableWidget()
        self.market_table.setObjectName("MarketTable")
        self.market_table.setColumnCount(len(headers))
        self.market_table.setHorizontalHeaderLabels(headers)
        self.market_table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.market_table.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.SingleSelection
        )
        self.market_table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.market_table.verticalHeader().setVisible(False)
        self.market_table.setAlternatingRowColors(True)
        self.market_table.setSortingEnabled(False)
        self.market_table.itemSelectionChanged.connect(self._table.on_selection_changed)
        self.market_table.setContextMenuPolicy(
            QtCore.Qt.ContextMenuPolicy.CustomContextMenu
        )
        self.market_table.customContextMenuRequested.connect(self._actions.show_context_menu)
        if self.config.table_header_sortable:
            self.market_table.horizontalHeader().setSortIndicatorShown(True)
            self.market_table.horizontalHeader().setSectionsClickable(True)

        header = self.market_table.horizontalHeader()
        self._table.apply_header_layout(column_count=len(headers))

        self.quote_name_label = QtWidgets.QLabel("—")
        self.quote_name_label.setObjectName("QuoteHeader")
        self.quote_code_label = QtWidgets.QLabel("")
        self.quote_price_label = QtWidgets.QLabel("—")
        self.quote_price_label.setObjectName("QuoteHeader")
        self.quote_change_label = QtWidgets.QLabel("")
        if self.config.hide_quote_header:
            self.quote_name_label.hide()
            self.quote_code_label.hide()
            self.quote_price_label.hide()
            self.quote_change_label.hide()
        elif self.config.use_local_table:
            self.quote_price_label.hide()
            self.quote_change_label.hide()

        quote_info = QtWidgets.QHBoxLayout()
        quote_info.addWidget(self.quote_name_label)
        quote_info.addWidget(self.quote_code_label)
        quote_info.addStretch()
        quote_info.addWidget(self.quote_price_label)
        quote_info.addWidget(self.quote_change_label)

        self.quote_sub_info = QtWidgets.QHBoxLayout()
        self._open_label = QtWidgets.QLabel("")
        self._high_label = QtWidgets.QLabel("")
        self._low_label = QtWidgets.QLabel("")
        self._volume_label = QtWidgets.QLabel("")
        for lbl in (self._open_label, self._high_label, self._low_label, self._volume_label):
            lbl.setObjectName("QuoteSubInfo")
            lbl.setStyleSheet(f"color: {NAV_MUTED_COLOR}; font-size: 12px;")
        self.quote_sub_info.addStretch()
        self.quote_sub_info.addWidget(self._open_label)
        self.quote_sub_info.addWidget(self._high_label)
        self.quote_sub_info.addWidget(self._low_label)
        self.quote_sub_info.addWidget(self._volume_label)

        if self.config.show_chart_tabs:
            self.chart_panel = ChartPanel()
            self.chart_panel.tab_changed.connect(self._on_chart_tab_changed)
            self._on_chart_tab_changed(self.chart_panel.current_tab_index())
            chart_widget = self.chart_panel
        elif not self.config.show_kline:
            chart_widget = None
        else:
            self.chart = create_daily_chart()
            chart_frame = QtWidgets.QWidget()
            chart_frame.setObjectName("ChartFrame")
            chart_frame.setStyleSheet(CHART_FRAME_STYLESHEET)
            frame_layout = QtWidgets.QVBoxLayout(chart_frame)
            frame_layout.setContentsMargins(4, 4, 4, 4)
            frame_layout.setSpacing(0)

            self.chart_hint = QtWidgets.QLabel("选中标的后显示日K")
            self.chart_hint.setObjectName("ChartHint")
            self.chart_hint.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

            frame_layout.addWidget(MaLegendBar())
            frame_layout.addWidget(self.chart, stretch=1)
            frame_layout.addWidget(self.chart_hint)
            chart_widget = chart_frame

        if self.config.show_kline:
            chart_row = QtWidgets.QHBoxLayout()
            chart_row.setSpacing(6)
            if chart_widget is not None:
                chart_row.addWidget(chart_widget, stretch=1)
            if self.config.show_depth_panel:
                self.depth_panel = DepthPanel()
                chart_row.addWidget(self.depth_panel)

            right_panel = QtWidgets.QVBoxLayout()
            right_panel.addLayout(quote_info)
            if self.config.column_configurable:
                right_panel.addLayout(self.quote_sub_info)
            if self.config.show_diagnose_panel:
                self.diagnose_panel = DiagnosePanel()
                self.diagnose_panel.refresh_requested.connect(self.run_diagnose_for_selected)
                right_panel.addWidget(self.diagnose_panel)
            right_panel.addLayout(chart_row, stretch=1)

            splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
            self._splitter = splitter
            center_widget = QtWidgets.QWidget()
            center_layout = QtWidgets.QVBoxLayout(center_widget)
            center_layout.setContentsMargins(0, 0, 0, 0)
            center_layout.addLayout(toolbar)
            if self.stats_label is not None:
                center_layout.addWidget(self.stats_label)
            center_layout.addWidget(self.market_table)
            center_layout.addLayout(self.pagination_bar)
            splitter.addWidget(center_widget)

            right_widget = QtWidgets.QWidget()
            right_widget.setLayout(right_panel)
            right_widget.setMinimumWidth(560 if self.config.show_depth_panel else 420)
            splitter.addWidget(right_widget)
            splitter.setStretchFactor(0, 3)
            splitter.setStretchFactor(1, 2)
        else:
            # 市场页：单栏全宽布局
            splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
            center_widget = QtWidgets.QWidget()
            center_layout = QtWidgets.QVBoxLayout(center_widget)
            center_layout.setContentsMargins(0, 0, 0, 0)
            center_layout.addLayout(toolbar)
            if self.stats_label is not None:
                center_layout.addWidget(self.stats_label)
            center_layout.addWidget(self.market_table)
            splitter.addWidget(center_widget)

        self.status_label = QtWidgets.QLabel("就绪")
        self.refresh_hint_label = QtWidgets.QLabel(
            quote_refresh_hint(
                auto_refresh=self.config.auto_refresh_quotes,
                refresh_ms=self.config.quote_refresh_ms,
                quote_source=self.config.quote_source,
            )
        )
        self.refresh_hint_label.setStyleSheet(f"color: {NAV_MUTED_COLOR};")

        bottom_bar = QtWidgets.QHBoxLayout()
        bottom_bar.setContentsMargins(8, 2, 8, 4)
        bottom_bar.addWidget(self.status_label, stretch=1)
        bottom_bar.addStretch()
        bottom_bar.addWidget(self.home_button)
        bottom_bar.addWidget(self.prev_page_button)
        bottom_bar.addWidget(self.page_label)
        bottom_bar.addWidget(self.page_jump_input)
        bottom_bar.addWidget(self.page_total_label)
        bottom_bar.addWidget(self.next_page_button)
        bottom_bar.addWidget(self.end_button)
        bottom_bar.addStretch()
        bottom_bar.addWidget(self.refresh_hint_label)

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(splitter, stretch=1)
        root.addLayout(bottom_bar)

    def activate(self) -> None:
        self._active = True
        if self.chart_panel is not None:
            self.chart_panel.set_active(True)
        if self.config.use_quote_stream:
            self._stream.start()
        if self.config.show_add_watchlist_button:
            self._watchlist.refresh_keys()
        if self.config.use_local_table:
            removed = cleanup_invalid_daily_bars()
            if removed:
                symbols = "、".join(
                    format_vt_symbol_cn(symbol, exchange) for symbol, exchange in removed[:5]
                )
                suffix = "..." if len(removed) > 5 else ""
                self.status_label.setText(f"已清理 {len(removed)} 条无效日K：{symbols}{suffix}")
        self._local.refresh_meta()
        if self.current_item is not None and self.chart_panel is not None:
            quote = self.quote_map.get(self.current_item.tickflow_symbol)
            self.chart_panel.load_item(self.current_item, quote=quote)
        self.load_stock_list()
        self._restore_splitter()

    def deactivate(self) -> None:
        self._save_splitter()
        self._save_column_config()
        self._active = False
        self._bars_generation += 1
        self._depth_generation += 1
        self._gap_generation += 1
        if self.chart_panel is not None:
            self.chart_panel.set_active(False)
        self._stream.stop()
        self._quote_timer.stop()
        for attr in (
            "_load_worker",
            "_market_worker",
            "_sync_worker",
            "_bars_worker",
            "_download_worker",
            "_gap_worker",
            "_quotes_worker",
            "_depth_worker",
            "_diagnose_worker",
        ):
            self._wait_worker_release(attr)

    def _splitter_settings_key(self) -> str:
        return f"quotes/splitter/{self.page_name}"

    def _column_settings_key(self) -> str:
        return self._table.column_settings_key()

    def _save_splitter(self) -> None:
        if self._splitter is None:
            return
        settings = QtCore.QSettings("vnpy_ashare", "ZakTerminal")
        settings.setValue(self._splitter_settings_key(), self._splitter.saveState())

    def _restore_splitter(self) -> None:
        if self._splitter is None:
            return
        settings = QtCore.QSettings("vnpy_ashare", "ZakTerminal")
        state = settings.value(self._splitter_settings_key())
        if state is not None:
            self._splitter.restoreState(state)

    def _save_column_config(self) -> None:
        self._table.save_column_config()

    def _restore_column_config(self) -> None:
        self._table.restore_column_config()

    def refresh_local_meta(self) -> None:
        self._local.refresh_meta()

    def _is_daily_local_scope(self) -> bool:
        return self._local.is_daily_scope()

    def _local_scope_label(self) -> str:
        return self._local.scope_label()

    def _on_local_period_changed(self, _index: int) -> None:
        self._local.on_period_changed()

    def _set_pagination_visible(self, visible: bool) -> None:
        self._pagination.set_visible(visible)

    def _market_page_count(self) -> int:
        return self._pagination.page_count()

    def _update_pagination_controls(self) -> None:
        self._pagination.update_controls()

    def _go_prev_page(self) -> None:
        self._pagination.go_prev()

    def _go_next_page(self) -> None:
        self._pagination.go_next()

    def _go_home_page(self) -> None:
        self._pagination.go_home()

    def _go_end_page(self) -> None:
        self._pagination.go_end()

    def _page_jump(self) -> None:
        self._pagination.jump()

    def _on_board_changed(self, _index: int) -> None:
        self._pagination.on_board_changed()

    def _format_market_status(self, result: MarketPageResult) -> str:
        return self._pagination.format_status(result)

    def _refresh_market_clicked(self) -> None:
        self.load_market_page(quiet=False)

    def load_market_page(self, *, quiet: bool = False) -> None:
        if not self._active or not self.config.use_market_rank:
            return

        if not universe_exists():
            self.display_stocks = []
            self.market_table.setRowCount(0)
            self._market_total = 0
            self._update_pagination_controls()
            self.status_label.setText("A 股列表未同步，请点击「同步 A 股列表」")
            return

        if self._thread_active(self._market_worker):
            return

        self._load_generation += 1
        generation = self._load_generation
        keyword = self.search_edit.text().strip()
        if quiet:
            if self._thread_active(self._quotes_worker):
                return
        else:
            self._set_busy(True)
            self.status_label.setText("正在加载市场数据...")

        worker = MarketPageLoadWorker(
            keyword=keyword,
            page=self._market_page,
            page_size=self.config.market_page_size,
            board=self._market_board,
        )
        self._market_worker = worker

        def on_finished(result: object) -> None:
            if self._market_worker is worker:
                self._market_worker = None
            if generation != self._load_generation or not self._active:
                return
            if not isinstance(result, MarketPageResult):
                return

            self.display_stocks = result.items
            self.quote_map = dict(result.quotes)
            self._market_total = result.total
            self._apply_default_table_sort = True
            self._sync_market_quotes_to_cache(result)
            if not quiet:
                self._set_busy(False)
            self._render_table()
            self._update_pagination_controls()
            self.status_label.setText(self._format_market_status(result))

            if self.config.auto_refresh_quotes:
                self._quote_timer.start()
            else:
                self._quote_timer.stop()

        def on_failed(msg: str) -> None:
            if self._market_worker is worker:
                self._market_worker = None
            if generation != self._load_generation or not self._active:
                return
            if not quiet:
                self._set_busy(False)
                self.status_label.setText(f"加载失败: {msg}")

        worker.finished.connect(on_finished)
        worker.failed.connect(on_failed)
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        worker.start()

    def load_stock_list(self) -> None:
        if not self._active:
            return

        if self.config.use_market_rank:
            self._market_page = 0
            self.load_market_page()
            return

        self._load_generation += 1
        generation = self._load_generation
        scope_key = self.config.scope_key

        if scope_key == "全部A股" and not universe_exists():
            self.all_stocks = []
            self.display_stocks = []
            self.market_table.setRowCount(0)
            self.status_label.setText("A 股列表未同步，请点击「同步 A 股列表」")
            return

        self._set_busy(True)
        self.status_label.setText(f"正在加载{self.page_name}...")
        self.market_table.setRowCount(0)

        worker = UniverseLoadWorker(scope_key, local_scope=self._local_scope)
        self._load_worker = worker

        def on_finished(stocks: list) -> None:
            if self._load_worker is worker:
                self._load_worker = None
            if generation != self._load_generation or not self._active:
                return
            self.all_stocks = stocks
            self._set_busy(False)
            self.apply_filter()

        def on_failed(msg: str) -> None:
            if self._load_worker is worker:
                self._load_worker = None
            if generation != self._load_generation or not self._active:
                return
            self._set_busy(False)
            self.status_label.setText(f"加载失败: {msg}")

        worker.finished.connect(on_finished)
        worker.failed.connect(on_failed)
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        worker.start()

    def apply_filter(self) -> None:
        self._table.apply_filter()

    def _stock_at_row(self, row: int) -> StockItem | None:
        return self._table.stock_at_row(row)

    def _selected_stock_key(self) -> tuple[str, Exchange] | None:
        return self._table.selected_stock_key()

    def _select_stock_key(self, key: tuple[str, Exchange]) -> None:
        self._table.select_stock_key(key)

    def _render_table(self, *, preserve_selection: bool = True) -> None:
        self._table.render_table(preserve_selection=preserve_selection)

    def _update_stats(self) -> None:
        self._table.update_stats()

    def _refresh_table_quotes(self) -> None:
        self._table.refresh_table_quotes()

    def _on_table_selection(self) -> None:
        self._table.on_selection_changed()

    def _show_column_menu(self) -> None:
        self._table.show_column_menu()

    def _on_column_toggle(self, key: str, checked: bool) -> None:
        self._table.on_column_toggle(key, checked)

    def _on_tail_column_toggle(self, key: str, checked: bool) -> None:
        self._table.on_tail_column_toggle(key, checked)

    def _rebuild_table(self) -> None:
        self._table.rebuild_table()

    def _sync_market_quotes_to_cache(self, result: object) -> None:
        """将市场页行情写入 session_context，供 AI 选股工具使用。"""
        if not hasattr(result, "items") or not hasattr(result, "quotes"):
            return
        from vnpy_ashare.ai.session_context import set_market_quotes_cache

        set_market_quotes_cache(result.items, dict(result.quotes))

    def _emit_ai_context(self) -> None:
        self._actions.emit_ai_context()

    def _use_quote_stream(self) -> bool:
        return self._stream.use_stream()

    def _start_quote_stream(self) -> None:
        self._stream.start()

    def _stop_quote_stream(self) -> None:
        self._stream.stop()

    def _sync_stream_subscriptions(self) -> None:
        self._stream.sync_subscriptions()

    def _sync_stream_depth_subscription(self) -> None:
        self._stream.sync_depth_subscription()

    def _on_stream_quotes(self, quotes: dict) -> None:
        self._stream.on_quotes(quotes)

    def _on_stream_depth(self, depth: DepthSnapshot) -> None:
        self._stream.on_depth(depth)

    def _on_stream_depth_denied(self, _message: str) -> None:
        self._stream.on_depth_denied(_message)

    def _on_stream_disconnected(self) -> None:
        self._stream.on_disconnected()

    def _on_stream_error(self, _message: str) -> None:
        self._stream.on_error(_message)

    def _refresh_charts_only(self) -> None:
        self._actions.refresh_charts_only()

    def refresh_depth(self) -> None:
        self._actions.refresh_depth()

    def _refresh_watchlist_keys(self) -> None:
        self._watchlist.refresh_keys()

    def _on_chart_tab_changed(self, index: int) -> None:
        self._actions.on_chart_tab_changed(index)

    def _update_action_buttons(self) -> None:
        self._actions.update_action_buttons()

    def _get_main_engine(self):
        parent = self.parent()
        if parent is not None and hasattr(parent, "main_engine"):
            return parent.main_engine
        return None

    def _get_watchlist_service(self):
        from vnpy_ashare.engine_access import get_service

        return get_service(self._get_main_engine(), "watchlist_service")

    def _get_analysis_service(self):
        from vnpy_ashare.engine_access import get_service

        return get_service(self._get_main_engine(), "analysis_service")

    def run_diagnose_for_selected(self) -> None:
        self._actions.run_diagnose_for_selected()

    def _ask_ai_for_diagnose(self) -> None:
        self._actions.ask_ai_for_diagnose()

    def _ask_ai_for_technical(self) -> None:
        self._actions.ask_ai_for_technical()

    def _ask_ai_for_signals(self) -> None:
        self._actions.ask_ai_for_signals()

    def _ask_ai_for_trend(self) -> None:
        self._actions.ask_ai_for_trend()

    def _on_diagnose_finished(self, payload: dict) -> None:
        self._actions.on_diagnose_finished(payload)

    def _on_diagnose_failed(self, message: str) -> None:
        self._actions.on_diagnose_failed(message)

    def open_backtest_for_selected(self) -> None:
        self._actions.open_backtest_for_selected()

    def add_to_watchlist(self) -> None:
        self._watchlist.add_selected()

    def remove_from_watchlist(self) -> None:
        self._watchlist.remove_selected()

    def _on_context_menu(self, pos: QtCore.QPoint) -> None:
        self._actions.show_context_menu(pos)

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        """上下方向键切换选中股票。"""
        if event.key() in (QtCore.Qt.Key.Key_Up, QtCore.Qt.Key.Key_Down):
            table = self.market_table
            if table.rowCount() == 0:
                return
            current = table.currentRow()
            if event.key() == QtCore.Qt.Key.Key_Up:
                next_row = current - 1 if current > 0 else 0
            else:
                next_row = current + 1 if current < table.rowCount() - 1 else table.rowCount() - 1
            if next_row != current and next_row >= 0:
                table.selectRow(next_row)
            return
        super().keyPressEvent(event)

    def _update_quote_header(self, item: StockItem) -> None:
        self._actions.update_quote_header(item)

    def refresh_quotes(self) -> None:
        self._actions.refresh_quotes()

    def _refresh_quotes_rest(self) -> None:
        self._actions.refresh_quotes_rest()

    def _set_chart_hint(self, text: str | None) -> None:
        self._local.set_chart_hint(text)

    def _update_coverage_hint(self, item: StockItem) -> None:
        self._local.update_coverage_hint(item)

    def _check_bar_gaps(self, item: StockItem) -> None:
        self._local.check_bar_gaps(item)

    def _refresh_row_for_item(self, item: StockItem) -> None:
        self._table.refresh_row_for_item(item)

    def show_kline(self, item: StockItem) -> None:
        self._local.show_kline(item)

    def sync_universe_clicked(self) -> None:
        if self._thread_active(self._sync_worker):
            return
        self._set_busy(True)
        self.status_label.setText("后台同步 A 股列表...")

        worker = UniverseSyncWorker()
        self._sync_worker = worker

        def on_finished(_path: str) -> None:
            if self._sync_worker is worker:
                self._sync_worker = None
            self._set_busy(False)
            self.status_label.setText("A 股列表同步完成")
            if self._active:
                self.load_stock_list()

        def on_failed(msg: str) -> None:
            if self._sync_worker is worker:
                self._sync_worker = None
            self._set_busy(False)
            self.status_label.setText(f"同步失败: {msg}")

        worker.finished.connect(on_finished)
        worker.failed.connect(on_failed)
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        worker.start()

    def download_selected(self) -> None:
        self._local.download_selected()

    def _run_minute_download(
        self,
        *,
        mode: str = "full",
        action_label: str = "下载",
    ) -> None:
        self._local.run_minute_download(mode=mode, action_label=action_label)

    def fill_selected(self) -> None:
        self._local.fill_selected()

    def redownload_selected(self) -> None:
        self._local.redownload_selected()

    def _run_download(self, *, mode: str, action_label: str) -> None:
        self._local.run_download(mode=mode, action_label=action_label)

    def _set_busy(self, busy: bool) -> None:
        self.search_edit.setEnabled(not busy)
        if self.config.use_local_table:
            self.local_period_combo.setEnabled(not busy)
        if self.config.show_board_filter:
            self.board_combo.setEnabled(not busy)
        if self.config.use_market_rank:
            self.refresh_quotes_button.setEnabled(not busy)
        if self.config.show_sync_button:
            self.sync_button.setEnabled(not busy)
        if self.config.use_market_rank:
            self._pagination.update_busy_state(busy)
        if busy:
            if self.config.show_download_button:
                self.download_button.setEnabled(False)
            if self.config.show_fill_button:
                self.fill_button.setEnabled(False)
            if self.config.show_redownload_button:
                self.redownload_button.setEnabled(False)
            if self.config.show_add_watchlist_button:
                self.add_watchlist_button.setEnabled(False)
            if self.config.show_remove_watchlist_button:
                self.remove_watchlist_button.setEnabled(False)
            if self.config.show_watchlist_move_buttons:
                self.move_watchlist_up_button.setEnabled(False)
                self.move_watchlist_down_button.setEnabled(False)
        else:
            self._update_action_buttons()
        self.market_table.setEnabled(not busy)
