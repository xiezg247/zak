"""行情列表页：市场 / 自选 / 本地 各自独立。"""

from __future__ import annotations

from typing import Literal

from vnpy.event import Event, EventEngine

from vnpy_ashare.events import EVENT_OPEN_BACKTEST, BacktestRequest
from vnpy.trader.constant import Exchange, Interval
from vnpy.trader.object import BarData
from vnpy.trader.database import get_database
from vnpy.trader.ui import QtCore, QtGui, QtWidgets

from vnpy_ashare.bar_health import (
    BarGapResult,
    BarHealthStatus,
    BarMeta,
    format_gap_ranges,
    format_meta_date,
    format_meta_datetime,
    list_status,
    status_label,
)
from vnpy_ashare.bar_store import iter_bar_overviews
from vnpy_ashare.bars import cleanup_invalid_daily_bars
from vnpy_ashare.minute_periods import (
    DEFAULT_MINUTE_DOWNLOAD_MONTHS,
    LOCAL_SCOPE_OPTIONS,
    is_daily_scope,
    scope_display,
)
from vnpy_ashare.calendar import last_trading_day
from vnpy_ashare.config import format_vt_symbol_cn
from vnpy_ashare.quotes import QuoteSnapshot
from vnpy_ashare.quotes.depth_snapshot import DepthSnapshot
from vnpy_ashare.quotes.tickflow_stream import TickflowStreamBridge, can_use_tickflow_stream
from vnpy_ashare.ui.styles import FALL_COLOR, FLAT_COLOR, NAV_MUTED_COLOR, RISE_COLOR, apply_toolbar_combo_style
from vnpy_ashare.ui.worker import (
    BarGapCheckWorker,
    BarsLoadWorker,
    DepthRefreshWorker,
    DownloadWorker,
    LoadedBars,
    MarketPageLoadWorker,
    MarketPageResult,
    MinuteDownloadWorker,
    ScopeBarsLoadWorker,
    QuotesRefreshWorker,
    UniverseLoadWorker,
    UniverseSyncWorker,
)
from vnpy_ashare.app_db import (
    add_watchlist_item,
    load_watchlist_rows,
    move_watchlist_item,
    remove_watchlist_item,
    universe_exists,
)
from vnpy_ashare.models import StockItem
from vnpy_ashare.quote_time import format_batch_updated_at
from vnpy_ashare.ui.chart_panel import ChartPanel, DAILY_TAB_INDEX, MINUTE_TAB_INDEX
from vnpy_ashare.ui.chart_style import CHART_FRAME_STYLESHEET
from vnpy_ashare.ui.ma_legend import MaLegendBar
from vnpy_ashare.ui.depth_panel import DepthPanel
from vnpy_ashare.ui.quote_columns import (
    LOCAL_TABLE_HEADERS,
    QUOTE_TABLE_COLUMNS,
    build_local_data_row,
    build_quote_row,
    quote_column_index,
)
from vnpy_ashare.ui.sortable_table import SortableTableItem
from vnpy_ashare.ui.quotes_chart import AshareChartWidget, create_daily_chart, prepare_chart_bars
from vnpy_ashare.ai.context import build_quote_context
from vnpy_ashare.ui.quotes_config import (
    MAX_DISPLAY_ROWS,
    PAGE_CONFIGS,
    quote_refresh_hint,
    SEARCH_DEBOUNCE_MS,
    TABLE_HEADERS_LOCAL,
    TABLE_HEADERS_WITH_LOCAL,
)

STATUS_OK_COLOR = "#3ddc84"
STATUS_STALE_COLOR = "#f0b429"
STATUS_GAP_COLOR = "#ff5c5c"


def should_apply_loaded_bars(
    *,
    generation: int,
    current_generation: int,
    request_id: int,
    current_request_id: int,
    target_key: tuple[str, Exchange],
    current_key: tuple[str, Exchange] | None,
    target_scope: str,
    current_scope: str,
    loaded_key: tuple[str, Exchange] | None = None,
) -> bool:
    """K 线回调是否应写入图表（标的、周期、generation 须一致）。"""
    if generation != current_generation:
        return False
    if request_id != current_request_id:
        return False
    if current_key is None or current_key != target_key:
        return False
    if target_scope != current_scope:
        return False
    if loaded_key is not None and loaded_key != target_key:
        return False
    return True


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
        try:
            if worker.isRunning():
                worker.wait(timeout_ms)
        except RuntimeError:
            pass
        setattr(self, attr, None)

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
        self._watchlist_keys: set[tuple[str, Exchange]] = set()
        self._load_generation = 0
        self._bars_generation = 0
        self._bars_request_id = 0
        self._active = False
        self._market_page = 0
        self._market_total = 0
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
        self._depth_generation = 0
        self._depth_permission_denied = False
        self.depth_panel: DepthPanel | None = None
        self.chart_panel: ChartPanel | None = None
        self.chart_hint: QtWidgets.QLabel | None = None
        self._stream_bridge: TickflowStreamBridge | None = None
        self._stream_fallback = False
        self._local_scope = "daily"

        self._search_timer = QtCore.QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(SEARCH_DEBOUNCE_MS)
        self._search_timer.timeout.connect(self.apply_filter)

        self._quote_timer = QtCore.QTimer(self)
        self._quote_timer.setInterval(self.config.quote_refresh_ms)
        self._quote_timer.timeout.connect(self.refresh_quotes)

        self._init_ui()

    def _init_ui(self) -> None:
        if self.config.use_local_table:
            headers = LOCAL_TABLE_HEADERS
        elif self.config.show_local_column:
            headers = TABLE_HEADERS_WITH_LOCAL
        else:
            headers = TABLE_HEADERS_LOCAL

        self.search_edit = QtWidgets.QLineEdit()
        self.search_edit.setObjectName("SearchBox")
        self.search_edit.setPlaceholderText(self.config.search_placeholder)
        self.search_edit.textChanged.connect(lambda _: self._search_timer.start())

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
        self.add_watchlist_button.clicked.connect(self.add_to_watchlist)
        self.add_watchlist_button.setEnabled(False)
        self.add_watchlist_button.setVisible(self.config.show_add_watchlist_button)

        self.remove_watchlist_button = QtWidgets.QPushButton("移出自选")
        self.remove_watchlist_button.clicked.connect(self.remove_from_watchlist)
        self.remove_watchlist_button.setEnabled(False)
        self.remove_watchlist_button.setVisible(self.config.show_remove_watchlist_button)

        self.move_watchlist_up_button = QtWidgets.QPushButton("上移")
        self.move_watchlist_up_button.clicked.connect(lambda: self._move_watchlist_selected("up"))
        self.move_watchlist_up_button.setEnabled(False)
        self.move_watchlist_up_button.setVisible(self.config.show_watchlist_move_buttons)

        self.move_watchlist_down_button = QtWidgets.QPushButton("下移")
        self.move_watchlist_down_button.clicked.connect(lambda: self._move_watchlist_selected("down"))
        self.move_watchlist_down_button.setEnabled(False)
        self.move_watchlist_down_button.setVisible(self.config.show_watchlist_move_buttons)

        self.backtest_button = QtWidgets.QPushButton("策略回测")
        self.backtest_button.clicked.connect(self.open_backtest_for_selected)
        self.backtest_button.setEnabled(False)
        self.backtest_button.setVisible(self.config.show_backtest_button)

        self.refresh_quotes_button = QtWidgets.QPushButton("刷新行情")
        self.refresh_quotes_button.clicked.connect(self._refresh_market_clicked)
        self.refresh_quotes_button.setVisible(self.config.use_market_rank)

        toolbar = QtWidgets.QHBoxLayout()
        toolbar.addWidget(self.search_edit, stretch=1)
        if self.config.use_market_rank:
            toolbar.addWidget(self.refresh_quotes_button)
        if self.config.show_sync_button:
            toolbar.addWidget(self.sync_button)
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

        self.prev_page_button = QtWidgets.QPushButton("上一页")
        self.prev_page_button.clicked.connect(self._go_prev_page)
        self.next_page_button = QtWidgets.QPushButton("下一页")
        self.next_page_button.clicked.connect(self._go_next_page)
        self.page_label = QtWidgets.QLabel("")

        self.pagination_bar = QtWidgets.QHBoxLayout()
        self.pagination_bar.addStretch()
        self.pagination_bar.addWidget(self.prev_page_button)
        self.pagination_bar.addWidget(self.page_label)
        self.pagination_bar.addWidget(self.next_page_button)
        self.pagination_bar.addStretch()
        self._set_pagination_visible(self.config.use_market_rank)

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
        self.market_table.itemSelectionChanged.connect(self._on_table_selection)
        if self.config.table_header_sortable:
            self.market_table.horizontalHeader().setSortIndicatorShown(True)
            self.market_table.horizontalHeader().setSectionsClickable(True)

        header = self.market_table.horizontalHeader()
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        if self.config.use_local_table:
            header.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeMode.Stretch)
            header.setSectionResizeMode(4, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(5, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(6, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(7, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        else:
            header.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(4, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        header.setStretchLastSection(False)

        self.quote_name_label = QtWidgets.QLabel("—")
        self.quote_name_label.setObjectName("QuoteHeader")
        self.quote_code_label = QtWidgets.QLabel("")
        self.quote_price_label = QtWidgets.QLabel("—")
        self.quote_price_label.setObjectName("QuoteHeader")
        self.quote_change_label = QtWidgets.QLabel("")
        if self.config.use_local_table:
            self.quote_price_label.hide()
            self.quote_change_label.hide()

        quote_info = QtWidgets.QHBoxLayout()
        quote_info.addWidget(self.quote_name_label)
        quote_info.addWidget(self.quote_code_label)
        quote_info.addStretch()
        quote_info.addWidget(self.quote_price_label)
        quote_info.addWidget(self.quote_change_label)

        if self.config.show_chart_tabs:
            self.chart_panel = ChartPanel()
            self.chart_panel.tab_changed.connect(self._on_chart_tab_changed)
            self._on_chart_tab_changed(self.chart_panel.current_tab_index())
            chart_widget = self.chart_panel
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

        chart_row = QtWidgets.QHBoxLayout()
        chart_row.setSpacing(6)
        chart_row.addWidget(chart_widget, stretch=1)
        if self.config.show_depth_panel:
            self.depth_panel = DepthPanel()
            chart_row.addWidget(self.depth_panel)

        right_panel = QtWidgets.QVBoxLayout()
        right_panel.addLayout(quote_info)
        right_panel.addLayout(chart_row, stretch=1)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        center_widget = QtWidgets.QWidget()
        center_layout = QtWidgets.QVBoxLayout(center_widget)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.addLayout(toolbar)
        center_layout.addWidget(self.market_table)
        center_layout.addLayout(self.pagination_bar)
        splitter.addWidget(center_widget)

        right_widget = QtWidgets.QWidget()
        right_widget.setLayout(right_panel)
        right_widget.setMinimumWidth(560 if self.config.show_depth_panel else 420)
        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        self.status_label = QtWidgets.QLabel("就绪")
        self.refresh_hint_label = QtWidgets.QLabel(
            quote_refresh_hint(
                auto_refresh=self.config.auto_refresh_quotes,
                refresh_ms=self.config.quote_refresh_ms,
                quote_source=self.config.quote_source,
            )
        )
        self.refresh_hint_label.setStyleSheet(f"color: {NAV_MUTED_COLOR};")

        status_bar = QtWidgets.QHBoxLayout()
        status_bar.setContentsMargins(4, 2, 8, 4)
        status_bar.addWidget(self.status_label, stretch=1)
        status_bar.addWidget(self.refresh_hint_label)

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(splitter, stretch=1)
        root.addLayout(status_bar)

    def activate(self) -> None:
        self._active = True
        if self.chart_panel is not None:
            self.chart_panel.set_active(True)
        if self.config.use_quote_stream:
            self._start_quote_stream()
        if self.config.show_add_watchlist_button:
            self._refresh_watchlist_keys()
        if self.config.use_local_table:
            removed = cleanup_invalid_daily_bars()
            if removed:
                symbols = "、".join(
                    format_vt_symbol_cn(symbol, exchange) for symbol, exchange in removed[:5]
                )
                suffix = "..." if len(removed) > 5 else ""
                self.status_label.setText(f"已清理 {len(removed)} 条无效日K：{symbols}{suffix}")
        self.refresh_local_meta()
        if self.current_item is not None and self.chart_panel is not None:
            quote = self.quote_map.get(self.current_item.tickflow_symbol)
            self.chart_panel.load_item(self.current_item, quote=quote)
        self.load_stock_list()

    def deactivate(self) -> None:
        self._active = False
        self._bars_generation += 1
        self._depth_generation += 1
        self._gap_generation += 1
        if self.chart_panel is not None:
            self.chart_panel.set_active(False)
        self._stop_quote_stream()
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
        ):
            self._wait_worker_release(attr)

    def refresh_local_meta(self) -> None:
        self.downloaded_keys = set()
        self.bar_meta = {}
        self.bar_list_status = {}
        for row in iter_bar_overviews(scope=self._local_scope):
            key = (row.symbol, row.exchange)
            meta = BarMeta(start=row.start, end=row.end, count=row.count)
            self.downloaded_keys.add(key)
            self.bar_meta[key] = meta
            self.bar_list_status[key] = list_status(meta)

    def _is_daily_local_scope(self) -> bool:
        return not self.config.use_local_table or is_daily_scope(self._local_scope)

    def _local_scope_label(self) -> str:
        return scope_display(self._local_scope)

    def _on_local_period_changed(self, _index: int) -> None:
        if not self.config.use_local_table:
            return
        value = self.local_period_combo.currentData()
        if not isinstance(value, str) or value == self._local_scope:
            return
        self._local_scope = value
        self._selected_gap_result = None
        self.refresh_local_meta()
        self.load_stock_list()
        if self.current_item is not None:
            self.show_kline(self.current_item)
            if self._is_daily_local_scope():
                self._check_bar_gaps(self.current_item)
            elif self.chart_hint is not None:
                self._update_coverage_hint(self.current_item)

    def _set_pagination_visible(self, visible: bool) -> None:
        self.prev_page_button.setVisible(visible)
        self.next_page_button.setVisible(visible)
        self.page_label.setVisible(visible)

    def _market_page_count(self) -> int:
        page_size = self.config.market_page_size
        if self._market_total <= 0 or page_size <= 0:
            return 1
        return max((self._market_total + page_size - 1) // page_size, 1)

    def _update_pagination_controls(self) -> None:
        if not self.config.use_market_rank:
            return
        page_count = self._market_page_count()
        current = min(self._market_page + 1, page_count)
        self.page_label.setText(f"第 {current} / {page_count} 页")
        self.prev_page_button.setEnabled(self._market_page > 0)
        self.next_page_button.setEnabled(self._market_page + 1 < page_count)

    def _go_prev_page(self) -> None:
        if self._market_page <= 0:
            return
        self._market_page -= 1
        self.load_market_page()

    def _go_next_page(self) -> None:
        if self._market_page + 1 >= self._market_page_count():
            return
        self._market_page += 1
        self.load_market_page()

    def _format_market_status(self, result: MarketPageResult) -> str:
        page_count = max(
            (result.total + result.page_size - 1) // result.page_size,
            1,
        )
        current = min(result.page + 1, page_count)
        if result.mode == "search":
            status = f"搜索匹配 {result.total} 只，第 {current}/{page_count} 页"
        else:
            status = f"共 {result.total} 只，第 {current}/{page_count} 页"
        batch_time = format_batch_updated_at(result.updated_at)
        if batch_time:
            status += f"，行情更新于 {batch_time}"
        elif result.total == 0:
            status += "（Redis 暂无行情，请运行 quote_collector）"
        return status

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
        if not self._active:
            return

        if self.config.use_market_rank:
            self._market_page = 0
            self.load_market_page()
            return

        keyword = self.search_edit.text().strip().lower()

        if self.config.require_keyword and not keyword:
            self.display_stocks = []
            self.market_table.setRowCount(0)
            self._quote_timer.stop()
            self.status_label.setText(
                f"共 {len(self.all_stocks)} 只 A 股，请输入关键词搜索（最多 {MAX_DISPLAY_ROWS} 条）"
            )
            return

        matched = (
            [s for s in self.all_stocks if keyword in s.search_key]
            if keyword
            else list(self.all_stocks)
        )
        self.display_stocks = matched[:MAX_DISPLAY_ROWS]
        self._render_table()
        if self.config.auto_refresh_quotes:
            self.refresh_quotes()
            self._quote_timer.start()
        else:
            self._quote_timer.stop()

        extra = f"，显示前 {MAX_DISPLAY_ROWS} 条" if len(matched) > MAX_DISPLAY_ROWS else ""
        if not matched and self.config.scope_key == "自选池":
            self.status_label.setText("自选池为空，请在市场页搜索标的并点击「加入自选」")
        elif not matched and self.config.use_local_table:
            label = self._local_scope_label()
            self.status_label.setText(f"暂无本地{label}，请在自选页下载")
        elif self.config.use_local_table:
            stale = sum(
                1
                for item in matched
                if self.bar_list_status.get(
                    (item.symbol, item.exchange),
                    BarHealthStatus.UNKNOWN,
                )
                in (BarHealthStatus.STALE, BarHealthStatus.GAPS)
            )
            status = f"{self.page_name}  共 {len(matched)} 只{extra}"
            if stale:
                status += f"，{stale} 只需补全"
            self.status_label.setText(status)
        else:
            self.status_label.setText(f"{self.page_name}  匹配 {len(matched)} 只{extra}")

    def _stock_at_row(self, row: int) -> StockItem | None:
        if row < 0:
            return None
        cell = self.market_table.item(row, 0)
        if cell is not None:
            item = cell.data(QtCore.Qt.ItemDataRole.UserRole)
            if isinstance(item, StockItem):
                return item
        if row < len(self.display_stocks):
            return self.display_stocks[row]
        return None

    def _selected_stock_key(self) -> tuple[str, Exchange] | None:
        if self.current_item is None:
            return None
        return (self.current_item.symbol, self.current_item.exchange)

    def _select_stock_key(self, key: tuple[str, Exchange]) -> None:
        for row in range(self.market_table.rowCount()):
            item = self._stock_at_row(row)
            if item and (item.symbol, item.exchange) == key:
                self.market_table.selectRow(row)
                return

    def _render_table(self, *, preserve_selection: bool = True) -> None:
        selected_key = self._selected_stock_key() if preserve_selection else None

        self.market_table.blockSignals(True)
        sorting_enabled = self.market_table.isSortingEnabled()
        self.market_table.setSortingEnabled(False)
        try:
            self.market_table.setRowCount(len(self.display_stocks))
            for row, item in enumerate(self.display_stocks):
                quote = self.quote_map.get(item.tickflow_symbol)
                self._set_row(row, item, quote)

            if selected_key:
                self._select_stock_key(selected_key)
            if self.market_table.currentRow() < 0 and self.display_stocks:
                self.market_table.selectRow(0)
        finally:
            self.market_table.blockSignals(False)

        if self.config.table_header_sortable:
            self.market_table.setSortingEnabled(True)
            if self._apply_default_table_sort:
                self._apply_default_table_sort = False
                symbol_col = quote_column_index("symbol")
                self.market_table.sortItems(
                    symbol_col,
                    QtCore.Qt.SortOrder.AscendingOrder,
                )
        elif sorting_enabled:
            self.market_table.setSortingEnabled(False)

        if self.market_table.currentRow() >= 0:
            self._on_table_selection()
        self._sync_stream_subscriptions()

    def _refresh_table_quotes(self) -> None:
        """仅更新行情列，避免重建表格导致选中行跳动。"""
        sorting_enabled = self.market_table.isSortingEnabled()
        if sorting_enabled:
            self.market_table.setSortingEnabled(False)
        self.market_table.blockSignals(True)
        try:
            for row in range(self.market_table.rowCount()):
                item = self._stock_at_row(row)
                if item is None:
                    continue
                quote = self.quote_map.get(item.tickflow_symbol)
                self._set_row(row, item, quote)
        finally:
            self.market_table.blockSignals(False)
        if sorting_enabled:
            self.market_table.setSortingEnabled(True)

    def _display_index(self, row: int) -> int:
        if self.config.use_market_rank:
            return self._market_page * self.config.market_page_size + row + 1
        return row + 1

    def _status_color(self, status: BarHealthStatus) -> str:
        if status == BarHealthStatus.OK:
            return STATUS_OK_COLOR
        if status == BarHealthStatus.STALE:
            return STATUS_STALE_COLOR
        if status == BarHealthStatus.GAPS:
            return STATUS_GAP_COLOR
        return FLAT_COLOR

    def _local_tail_values(self, item: StockItem) -> list[str]:
        key = (item.symbol, item.exchange)
        meta = self.bar_meta.get(key)
        status = self.bar_list_status.get(key, list_status(meta))
        minute = not self._is_daily_local_scope()
        return [
            format_meta_datetime(meta.start if meta else None, minute=minute),
            format_meta_datetime(meta.end if meta else None, minute=minute),
            str(meta.count) if meta else "—",
            status_label(status),
        ]

    def _quote_sort_key(
        self,
        column_key: str,
        item: StockItem,
        quote: QuoteSnapshot | None,
        index_text: str,
    ) -> float | str:
        if column_key == "index":
            return int(index_text)
        if column_key == "symbol":
            return item.symbol
        if column_key == "exchange":
            return item.exchange.value
        if column_key == "name":
            return (quote.name if quote and quote.name else item.name).lower()
        if quote is None:
            return float("-inf")
        numeric_map = {
            "last_price": quote.last_price,
            "change_pct": quote.change_pct,
            "change_amount": quote.change_amount,
            "amplitude": quote.amplitude,
            "turnover_rate": quote.turnover_rate,
            "volume": quote.volume,
            "amount": quote.amount,
            "high_price": quote.high_price,
            "low_price": quote.low_price,
            "open_price": quote.open_price,
            "prev_close": quote.prev_close,
        }
        if column_key in numeric_map:
            return numeric_map[column_key]
        if column_key == "trade_time":
            return quote.trade_time or ""
        return ""

    def _make_table_cell(
        self,
        text: str,
        *,
        item: StockItem | None = None,
        sort_key: float | str | None = None,
        color: str | None = None,
    ) -> QtWidgets.QTableWidgetItem:
        if self.config.table_header_sortable and sort_key is not None:
            cell: QtWidgets.QTableWidgetItem = SortableTableItem(text, sort_key)
        else:
            cell = QtWidgets.QTableWidgetItem(text)
        cell.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        if item is not None:
            cell.setData(QtCore.Qt.ItemDataRole.UserRole, item)
        if color is not None:
            cell.setForeground(QtGui.QColor(color))
        return cell

    def _set_local_row(self, row: int, item: StockItem) -> None:
        key = (item.symbol, item.exchange)
        meta = self.bar_meta.get(key)
        status = self.bar_list_status.get(key, list_status(meta))
        minute = not self._is_daily_local_scope()
        values = build_local_data_row(
            item,
            str(self._display_index(row)),
            start=format_meta_datetime(meta.start if meta else None, minute=minute),
            end=format_meta_datetime(meta.end if meta else None, minute=minute),
            count=str(meta.count) if meta else "—",
            status=status_label(status),
        )
        status_col = len(values) - 1
        for col, text in enumerate(values):
            cell = self._make_table_cell(
                text,
                item=item if col == 0 else None,
            )
            if col == status_col:
                cell.setForeground(QtGui.QColor(self._status_color(status)))
            self.market_table.setItem(row, col, cell)

    def _set_row(self, row: int, item: StockItem, quote: QuoteSnapshot | None) -> None:
        if self.config.use_local_table:
            self._set_local_row(row, item)
            return

        index_text = str(self._display_index(row))
        key = (item.symbol, item.exchange)
        if self.config.show_local_column:
            tail_value = "✓" if key in self.downloaded_keys else "—"
            tail_values = None
        elif self.config.show_fill_button and not self.config.use_local_table:
            tail_value = ""
            tail_values = self._local_tail_values(item)
        else:
            meta = self.bar_meta.get(key)
            count = meta.count if meta else 0
            tail_value = str(count) if count else "—"
            tail_values = None

        values, price_cols = build_quote_row(
            item,
            quote,
            index_text,
            tail_value,
            tail_values=tail_values,
        )
        color = FLAT_COLOR
        if quote:
            color = RISE_COLOR if quote.is_rise else FALL_COLOR if quote.is_fall else FLAT_COLOR

        status_col: int | None = None
        status: BarHealthStatus | None = None
        if tail_values is not None:
            status_col = len(values) - 1
            status = self.bar_list_status.get(key, list_status(self.bar_meta.get(key)))

        for col, text in enumerate(values):
            column_key = (
                QUOTE_TABLE_COLUMNS[col].key
                if col < len(QUOTE_TABLE_COLUMNS)
                else f"tail_{col - len(QUOTE_TABLE_COLUMNS)}"
            )
            sort_key = (
                self._quote_sort_key(column_key, item, quote, index_text)
                if col < len(QUOTE_TABLE_COLUMNS)
                else text
            )
            cell_color = None
            if quote and col in price_cols:
                cell_color = color
            if status_col is not None and col == status_col and status is not None:
                cell_color = self._status_color(status)
            cell = self._make_table_cell(
                text,
                item=item if col == 0 else None,
                sort_key=sort_key,
                color=cell_color,
            )
            self.market_table.setItem(row, col, cell)

    def _on_table_selection(self) -> None:
        rows = self.market_table.selectionModel().selectedRows()
        if not rows:
            return
        idx = rows[0].row()
        item = self._stock_at_row(idx)
        if item is None:
            return

        new_key = (item.symbol, item.exchange)
        old_key = self._selected_stock_key()
        self.current_item = item
        self._update_action_buttons()
        self._update_quote_header(item)
        if new_key != old_key:
            self._selected_gap_result = None
            self.show_kline(item)
            if self.config.show_fill_button and self._is_daily_local_scope():
                self._check_bar_gaps(item)
            if self.config.show_depth_panel:
                self.refresh_depth()
        self._sync_stream_depth_subscription()
        self._emit_ai_context()

    def _emit_ai_context(self) -> None:
        """更新 session_context（bridge，供 QuoteService/Skill 读取）。"""
        from vnpy_ashare.ai.session_context import set_ai_context
        quote = None
        bar_count = 0
        if self.current_item is not None:
            quote = self.quote_map.get(self.current_item.tickflow_symbol)
            key = (self.current_item.symbol, self.current_item.exchange)
            meta = self.bar_meta.get(key)
            bar_count = meta.count if meta else 0
        data = build_quote_context(
            page=self.page_name,
            item=self.current_item,
            quote=quote,
            bar_count=bar_count,
        )
        set_ai_context(data)

    def _use_quote_stream(self) -> bool:
        return (
            self.config.use_quote_stream
            and self._stream_bridge is not None
            and self._stream_bridge.is_connected
            and not self._stream_fallback
        )

    def _start_quote_stream(self) -> None:
        if self._stream_bridge is not None:
            return
        if not can_use_tickflow_stream():
            self._stream_fallback = True
            return
        bridge = TickflowStreamBridge(self)
        bridge.quotes_updated.connect(self._on_stream_quotes)
        bridge.depth_updated.connect(self._on_stream_depth)
        bridge.depth_permission_denied.connect(self._on_stream_depth_denied)
        bridge.disconnected.connect(self._on_stream_disconnected)
        bridge.error.connect(self._on_stream_error)
        self._stream_bridge = bridge
        self._stream_fallback = False
        bridge.start()

    def _stop_quote_stream(self) -> None:
        bridge = self._stream_bridge
        self._stream_bridge = None
        if bridge is None:
            return
        bridge.stop()
        bridge.deleteLater()

    def _sync_stream_subscriptions(self) -> None:
        if self._stream_bridge is None:
            return
        symbols = [item.tickflow_symbol for item in self.display_stocks]
        self._stream_bridge.set_quote_symbols(symbols)
        self._sync_stream_depth_subscription()

    def _sync_stream_depth_subscription(self) -> None:
        if self._stream_bridge is None:
            return
        if self._depth_permission_denied or self.current_item is None:
            self._stream_bridge.set_depth_symbol(None)
            return
        self._stream_bridge.set_depth_symbol(self.current_item.tickflow_symbol)

    def _on_stream_quotes(self, quotes: dict) -> None:
        if not self._active:
            return
        self._stream_fallback = False
        self.quote_map.update(quotes)
        self._refresh_table_quotes()
        if self.current_item:
            self._update_quote_header(self.current_item)
            if self.chart_panel is not None:
                self.chart_panel.update_quote(quotes.get(self.current_item.tickflow_symbol))
            self._emit_ai_context()

    def _on_stream_depth(self, depth: DepthSnapshot) -> None:
        if not self._active or self.depth_panel is None or self.current_item is None:
            return
        if depth.symbol != self.current_item.tickflow_symbol:
            return
        self.depth_panel.update_depth(depth)

    def _on_stream_depth_denied(self, _message: str) -> None:
        self._depth_permission_denied = True
        if self.depth_panel is not None:
            self.depth_panel.show_permission_denied("未开通市场深度权限")
        self._sync_stream_depth_subscription()

    def _on_stream_disconnected(self) -> None:
        self._stream_fallback = True

    def _on_stream_error(self, _message: str) -> None:
        self._stream_fallback = True
        self._stop_quote_stream()
        if self._active:
            self._refresh_quotes_rest()

    def _refresh_charts_only(self) -> None:
        current = self.current_item
        if current is None or self.chart_panel is None:
            return
        self.chart_panel.update_quote(self.quote_map.get(current.tickflow_symbol))
        self.chart_panel.refresh_active()

    def refresh_depth(self) -> None:
        if not self._active or not self.config.show_depth_panel or self.depth_panel is None:
            return
        if self._use_quote_stream():
            return
        if self._depth_permission_denied or not self.current_item:
            return
        if self._thread_active(self._depth_worker):
            return

        self._depth_generation += 1
        generation = self._depth_generation
        item = self.current_item
        target_key = (item.symbol, item.exchange)

        worker = DepthRefreshWorker(item)
        self._depth_worker = worker

        def on_finished(depth: object) -> None:
            if generation != self._depth_generation:
                return
            if self._depth_worker is worker:
                self._depth_worker = None
            if not self._active or self.current_item is None:
                return
            if (self.current_item.symbol, self.current_item.exchange) != target_key:
                return
            if isinstance(depth, DepthSnapshot):
                self.depth_panel.update_depth(depth)

        def on_permission_denied(message: str) -> None:
            if generation != self._depth_generation:
                return
            if self._depth_worker is worker:
                self._depth_worker = None
            self._depth_permission_denied = True
            self.depth_panel.show_permission_denied("未开通市场深度权限")

        def on_failed(_msg: str) -> None:
            if self._depth_worker is worker:
                self._depth_worker = None

        worker.finished.connect(on_finished)
        worker.permission_denied.connect(on_permission_denied)
        worker.failed.connect(on_failed)
        worker.finished.connect(worker.deleteLater)
        worker.permission_denied.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        worker.start()

    def _refresh_watchlist_keys(self) -> None:
        self._watchlist_keys = {
            (symbol, exchange) for symbol, exchange, _ in load_watchlist_rows()
        }

    def _on_chart_tab_changed(self, index: int) -> None:
        if self.config.show_download_button and self.config.show_chart_tabs:
            show = index in (DAILY_TAB_INDEX, MINUTE_TAB_INDEX)
            self.download_button.setVisible(show)
            if index == MINUTE_TAB_INDEX:
                self.download_button.setText("下载分K到本地")
            else:
                self.download_button.setText("下载日K到本地")
        self._update_action_buttons()

    def _update_action_buttons(self) -> None:
        item = self.current_item
        if self.config.show_download_button:
            if self.config.show_chart_tabs:
                on_download_tab = (
                    self.chart_panel is not None
                    and self.chart_panel.current_tab_index()
                    in (DAILY_TAB_INDEX, MINUTE_TAB_INDEX)
                )
                self.download_button.setVisible(on_download_tab)
                self.download_button.setEnabled(item is not None and on_download_tab)
            else:
                self.download_button.setEnabled(item is not None)
        if self.config.show_fill_button:
            if item is None:
                self.fill_button.setEnabled(False)
            else:
                key = (item.symbol, item.exchange)
                status = self.bar_list_status.get(key, list_status(self.bar_meta.get(key)))
                self.fill_button.setEnabled(
                    status in (BarHealthStatus.STALE, BarHealthStatus.GAPS)
                )
        if self.config.show_redownload_button:
            if item is None:
                self.redownload_button.setEnabled(False)
            else:
                key = (item.symbol, item.exchange)
                self.redownload_button.setEnabled(key in self.bar_meta)
        if self.config.show_add_watchlist_button:
            if item is None:
                self.add_watchlist_button.setEnabled(False)
            else:
                key = (item.symbol, item.exchange)
                self.add_watchlist_button.setEnabled(key not in self._watchlist_keys)
        if self.config.show_remove_watchlist_button:
            self.remove_watchlist_button.setEnabled(item is not None)
        if self.config.show_watchlist_move_buttons:
            index = self._watchlist_index(item) if item is not None else None
            total = len(self.all_stocks)
            self.move_watchlist_up_button.setEnabled(
                item is not None and index is not None and index > 0
            )
            self.move_watchlist_down_button.setEnabled(
                item is not None
                and index is not None
                and index + 1 < total
            )
        if self.config.show_backtest_button:
            self.backtest_button.setEnabled(item is not None)

    def open_backtest_for_selected(self) -> None:
        if not self.current_item or self.event_engine is None:
            return
        item = self.current_item
        quote = self.quote_map.get(item.tickflow_symbol)
        name = quote.name if quote and quote.name else item.name
        self.event_engine.put(
            Event(
                EVENT_OPEN_BACKTEST,
                BacktestRequest(
                    vt_symbol=item.vt_symbol,
                    source_page=self.page_name,
                    name=name,
                ),
            )
        )

    def add_to_watchlist(self) -> None:
        if not self.current_item:
            return
        item = self.current_item
        quote = self.quote_map.get(item.tickflow_symbol)
        name = quote.name if quote and quote.name else item.name
        if not add_watchlist_item(item.symbol, item.exchange, name):
            self.status_label.setText(f"{format_vt_symbol_cn(item.symbol, item.exchange)} 已在自选池")
            return
        self._refresh_watchlist_keys()
        self._update_action_buttons()
        self.status_label.setText(f"已加入自选：{format_vt_symbol_cn(item.symbol, item.exchange)}")

    def remove_from_watchlist(self) -> None:
        if not self.current_item:
            return
        item = self.current_item
        if not remove_watchlist_item(item.symbol, item.exchange):
            self.status_label.setText("移出失败：标的不在自选池")
            return
        self.current_item = None
        if self.depth_panel is not None:
            self.depth_panel.clear()
        self.status_label.setText(f"已移出自选：{format_vt_symbol_cn(item.symbol, item.exchange)}")
        self.load_stock_list()

    def _watchlist_index(self, item: StockItem) -> int | None:
        key = (item.symbol, item.exchange)
        for index, stock in enumerate(self.all_stocks):
            if (stock.symbol, stock.exchange) == key:
                return index
        return None

    def _move_watchlist_selected(self, direction: Literal["up", "down"]) -> None:
        if not self.current_item:
            return
        item = self.current_item
        key = (item.symbol, item.exchange)
        if not move_watchlist_item(item.symbol, item.exchange, direction=direction):
            return
        self.all_stocks = [
            StockItem(symbol=symbol, exchange=exchange, name=name)
            for symbol, exchange, name in load_watchlist_rows()
        ]
        self.apply_filter()
        self._select_stock_key(key)
        label = "上移" if direction == "up" else "下移"
        self.status_label.setText(
            f"{format_vt_symbol_cn(item.symbol, item.exchange)} 已{label}"
        )

    def _update_quote_header(self, item: StockItem) -> None:
        quote = self.quote_map.get(item.tickflow_symbol)
        self.quote_name_label.setText(quote.name if quote and quote.name else item.name)
        self.quote_code_label.setText(
            f"  {format_vt_symbol_cn(item.symbol, item.exchange)}"
        )

        if not quote:
            self.quote_price_label.setText("—")
            self.quote_change_label.setText("")
            return

        color = RISE_COLOR if quote.is_rise else FALL_COLOR if quote.is_fall else FLAT_COLOR
        self.quote_price_label.setText(f"{quote.last_price:.2f}")
        self.quote_price_label.setStyleSheet(f"color: {color};")
        self.quote_change_label.setText(
            f"  {quote.change_amount:+.2f}  ({quote.change_pct:+.2f}%)"
        )
        self.quote_change_label.setStyleSheet(f"color: {color}; font-size: 14px;")

    def refresh_quotes(self) -> None:
        if not self._active or not self.config.quote_source:
            return
        if self.config.use_market_rank:
            self._refresh_quotes_rest()
            return
        if not self.display_stocks:
            return
        if self._use_quote_stream():
            self._refresh_charts_only()
            return
        self._refresh_quotes_rest()

    def _refresh_quotes_rest(self) -> None:
        if not self.display_stocks:
            return
        if self._thread_active(self._quotes_worker):
            return

        if self.config.show_depth_panel:
            self.refresh_depth()

        worker = QuotesRefreshWorker(list(self.display_stocks), self.config.quote_source)
        self._quotes_worker = worker
        current = self.current_item

        def on_finished(quotes: dict) -> None:
            if self._quotes_worker is worker:
                self._quotes_worker = None
            if not self._active:
                return
            self.quote_map.update(quotes)
            self._refresh_table_quotes()
            if current:
                self._update_quote_header(current)
                if self.chart_panel is not None:
                    self.chart_panel.update_quote(quotes.get(current.tickflow_symbol))
                    self.chart_panel.refresh_active()

        def on_failed(_msg: str) -> None:
            if self._quotes_worker is worker:
                self._quotes_worker = None

        worker.finished.connect(on_finished)
        worker.failed.connect(on_failed)
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        worker.start()

    def _set_chart_hint(self, text: str | None) -> None:
        if self.chart_hint is None:
            return
        if text:
            self.chart_hint.setText(text)
            self.chart_hint.show()
        else:
            self.chart_hint.hide()

    def _update_coverage_hint(self, item: StockItem) -> None:
        if not self.config.show_fill_button or self.chart_hint is None:
            return
        key = (item.symbol, item.exchange)
        meta = self.bar_meta.get(key)
        scope_label = self._local_scope_label()
        if meta is None:
            self._set_chart_hint(f"暂无本地{scope_label}")
            return

        minute = not self._is_daily_local_scope()
        lines = [
            f"{scope_label}："
            f"{format_meta_datetime(meta.start, minute=minute)} ~ "
            f"{format_meta_datetime(meta.end, minute=minute)}，共 {meta.count} 根"
        ]
        status = self.bar_list_status.get(key, list_status(meta))
        if status == BarHealthStatus.STALE:
            latest = last_trading_day()
            lines.append(
                f"⚠️ 数据过期，最新应为 {latest.isoformat()}，请点击「补全到最新」"
            )
        elif (
            self._is_daily_local_scope()
            and status == BarHealthStatus.GAPS
            and self._selected_gap_result is not None
        ):
            gap_text = format_gap_ranges(self._selected_gap_result.gaps)
            lines.append(f"🔴 发现 {len(self._selected_gap_result.gaps)} 处断层：{gap_text}")
        self._set_chart_hint("\n".join(lines))

    def _check_bar_gaps(self, item: StockItem) -> None:
        if not self.config.show_fill_button or not self._is_daily_local_scope():
            return
        key = (item.symbol, item.exchange)
        meta = self.bar_meta.get(key)
        if meta is None:
            self._selected_gap_result = None
            self._update_coverage_hint(item)
            return

        if self._thread_active(self._gap_worker):
            self._wait_worker_release("_gap_worker")

        self._gap_generation += 1
        generation = self._gap_generation
        self._set_chart_hint("正在检查数据完整性...")

        worker = BarGapCheckWorker(item, meta)
        self._gap_worker = worker

        def on_finished(result: object) -> None:
            if generation != self._gap_generation:
                return
            if self._gap_worker is worker:
                self._gap_worker = None
            if not self._active or self.current_item is None:
                return
            if (self.current_item.symbol, self.current_item.exchange) != key:
                return
            if not isinstance(result, tuple) or len(result) != 2:
                return
            result_item, gap_result = result
            if (result_item.symbol, result_item.exchange) != key:
                return
            if not isinstance(gap_result, BarGapResult):
                return

            self._selected_gap_result = gap_result
            self.bar_list_status[key] = gap_result.status
            self._refresh_row_for_item(item)
            self._update_action_buttons()
            self._update_coverage_hint(item)

        def on_failed(_msg: str) -> None:
            if generation != self._gap_generation:
                return
            if self._gap_worker is worker:
                self._gap_worker = None
            if self.current_item is None:
                return
            if (self.current_item.symbol, self.current_item.exchange) != key:
                return
            self._set_chart_hint("完整性检查失败，仍可查看已有 K 线")

        worker.finished.connect(on_finished)
        worker.failed.connect(on_failed)
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        worker.start()

    def _clear_local_chart(self) -> None:
        chart = self.chart
        if isinstance(chart, AshareChartWidget):
            chart.configure_scope(minute=not self._is_daily_local_scope())
            chart.replace_history([])
        else:
            chart.clear_all()
            chart.move_to_right()

    def _render_local_chart(self, bars: list[BarData]) -> None:
        chart = self.chart
        minute = not self._is_daily_local_scope()
        if isinstance(chart, AshareChartWidget):
            chart.configure_scope(minute=minute)
            chart.replace_history(bars)
        else:
            chart.replace_history(prepare_chart_bars(bars))

    def _refresh_row_for_item(self, item: StockItem) -> None:
        for row in range(self.market_table.rowCount()):
            row_item = self._stock_at_row(row)
            if row_item is None:
                continue
            if (row_item.symbol, row_item.exchange) != (item.symbol, item.exchange):
                continue
            quote = self.quote_map.get(item.tickflow_symbol)
            self._set_row(row, item, quote)
            break

    def show_kline(self, item: StockItem) -> None:
        quote = self.quote_map.get(item.tickflow_symbol)
        if self.chart_panel is not None:
            self.chart_panel.load_item(item, quote=quote)
            return

        self._set_chart_hint(None)
        self._bars_generation += 1
        generation = self._bars_generation
        self._bars_request_id += 1
        request_id = self._bars_request_id
        target_key = (item.symbol, item.exchange)
        target_scope = self._local_scope

        self._wait_worker_release("_bars_worker")

        self._clear_local_chart()

        if self._is_daily_local_scope():
            worker = BarsLoadWorker(item)
        else:
            worker = ScopeBarsLoadWorker(item, scope=target_scope)
        self._bars_worker = worker

        def _should_apply(result: object) -> bool:
            if not self._active or self.current_item is None:
                return False
            current_key = (self.current_item.symbol, self.current_item.exchange)
            loaded_key = None
            if isinstance(result, LoadedBars):
                loaded_key = (result.item.symbol, result.item.exchange)
            return should_apply_loaded_bars(
                generation=generation,
                current_generation=self._bars_generation,
                request_id=request_id,
                current_request_id=self._bars_request_id,
                target_key=target_key,
                current_key=current_key,
                target_scope=target_scope,
                current_scope=self._local_scope,
                loaded_key=loaded_key,
            )

        def on_finished(result: object) -> None:
            if self._bars_worker is worker:
                self._bars_worker = None
            if not _should_apply(result):
                return
            scope_label = self._local_scope_label()
            if result is None:
                self._clear_local_chart()
                if self.config.show_fill_button:
                    self._set_chart_hint(f"暂无本地{scope_label}")
                else:
                    self._set_chart_hint(f"暂无本地{scope_label}，请点击「下载日K到本地」")
                return
            loaded: LoadedBars = result
            if loaded.bars:
                self._render_local_chart(loaded.bars)
                if self.config.show_fill_button:
                    self._update_coverage_hint(item)
                else:
                    self._set_chart_hint(None)
            else:
                self._clear_local_chart()
                if self.config.show_fill_button:
                    self._set_chart_hint(f"暂无本地{scope_label}")
                else:
                    self._set_chart_hint(f"暂无本地{scope_label}，请点击「下载日K到本地」")

        def on_failed(_msg: str) -> None:
            if self._bars_worker is worker:
                self._bars_worker = None

        worker.finished.connect(on_finished)
        worker.failed.connect(on_failed)
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        worker.start()

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
        if (
            self.config.show_chart_tabs
            and self.chart_panel is not None
            and self.chart_panel.current_tab_index() == MINUTE_TAB_INDEX
        ):
            self._run_minute_download(mode="full")
            return
        self._run_download(mode="full", action_label="下载")

    def _run_minute_download(
        self,
        *,
        mode: str = "full",
        action_label: str = "下载",
    ) -> None:
        if not self.current_item or self._thread_active(self._download_worker):
            return
        if self.chart_panel is None and not self.config.use_local_table:
            return

        item = self.current_item
        if self.config.use_local_table:
            period = self._local_scope
            period_label = self._local_scope_label()
        else:
            period = self.chart_panel.current_period()
            period_label = self.chart_panel.current_period_label()

        self._set_busy(True)
        if mode == "incremental":
            status_text = f"{action_label} {format_vt_symbol_cn(item.symbol, item.exchange)} {period_label}..."
        else:
            status_text = (
                f"{action_label} {format_vt_symbol_cn(item.symbol, item.exchange)} "
                f"{period_label}（近{DEFAULT_MINUTE_DOWNLOAD_MONTHS}个月）..."
            )
        self.status_label.setText(status_text)

        worker = MinuteDownloadWorker(item, period=period, mode=mode)
        self._download_worker = worker

        def on_finished(count: int) -> None:
            if self._download_worker is worker:
                self._download_worker = None
            self._set_busy(False)
            label = format_vt_symbol_cn(item.symbol, item.exchange)
            if self.config.use_local_table:
                self.refresh_local_meta()
                self.apply_filter()
            if self.chart_panel is not None:
                self.chart_panel.refresh_active()
            elif self.current_item is not None:
                self.show_kline(self.current_item)
            if mode == "incremental" and count == 0:
                self.status_label.setText(f"{label} 已是最新，无新增 K 线")
            elif action_label == "下载":
                self.status_label.setText(f"{label} 已下载 {count} 根{period_label}")
            else:
                self.status_label.setText(f"{label} {action_label}完成，新增 {count} 根")

        def on_failed(msg: str) -> None:
            if self._download_worker is worker:
                self._download_worker = None
            self._set_busy(False)
            self.status_label.setText(f"{action_label}分K失败: {msg}")

        worker.finished.connect(on_finished)
        worker.failed.connect(on_failed)
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        worker.start()

    def fill_selected(self) -> None:
        if self.config.use_local_table and not self._is_daily_local_scope():
            self._run_minute_download(mode="incremental", action_label="补全")
            return
        self._run_download(mode="incremental", action_label="补全")

    def redownload_selected(self) -> None:
        if self.config.use_local_table and not self._is_daily_local_scope():
            self._run_minute_download(mode="full", action_label="重新下载")
            return
        self._run_download(mode="full", action_label="重新下载")

    def _run_download(self, *, mode: str, action_label: str) -> None:
        if not self.current_item or self._thread_active(self._download_worker):
            return

        item = self.current_item
        self._set_busy(True)
        self.status_label.setText(
            f"{action_label} {format_vt_symbol_cn(item.symbol, item.exchange)} 日K..."
        )

        worker = DownloadWorker(item, mode=mode)
        self._download_worker = worker

        def on_finished(count: int) -> None:
            if self._download_worker is worker:
                self._download_worker = None
            self.refresh_local_meta()
            self.apply_filter()
            self.show_kline(item)
            if self.config.show_fill_button and self._is_daily_local_scope():
                self._check_bar_gaps(item)
            self._set_busy(False)
            label = format_vt_symbol_cn(item.symbol, item.exchange)
            if mode == "incremental" and count == 0:
                self.status_label.setText(f"{label} 已是最新，无新增 K 线")
            elif action_label == "下载":
                self.status_label.setText(f"{label} 已下载 {count} 根日K")
            else:
                self.status_label.setText(f"{label} {action_label}完成，新增 {count} 根日K")

        def on_failed(msg: str) -> None:
            if self._download_worker is worker:
                self._download_worker = None
            self._set_busy(False)
            self.status_label.setText(f"{action_label}失败: {msg}")

        worker.finished.connect(on_finished)
        worker.failed.connect(on_failed)
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        worker.start()

    def _set_busy(self, busy: bool) -> None:
        self.search_edit.setEnabled(not busy)
        if self.config.use_local_table:
            self.local_period_combo.setEnabled(not busy)
        if self.config.use_market_rank:
            self.refresh_quotes_button.setEnabled(not busy)
        if self.config.show_sync_button:
            self.sync_button.setEnabled(not busy)
        if self.config.use_market_rank:
            self.prev_page_button.setEnabled(not busy and self._market_page > 0)
            self.next_page_button.setEnabled(
                not busy and self._market_page + 1 < self._market_page_count()
            )
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
