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
from vnpy_ashare.calendar import last_trading_day
from vnpy_ashare.config import format_vt_symbol_cn
from vnpy_ashare.quotes import QuoteSnapshot
from vnpy_ashare.quotes.depth_snapshot import DepthSnapshot
from vnpy_ashare.ui.quotes.actions_controller import ActionsController
from vnpy_ashare.ui.quotes.batch_backtest_controller import WatchlistBatchBacktestController
from vnpy_ashare.ui.quotes.data_loader_controller import DataLoaderController
from vnpy_ashare.ui.quotes.local_data_controller import LocalDataController, should_apply_loaded_bars
from vnpy_ashare.ui.quotes.pagination_controller import MarketPaginationController
from vnpy_ashare.ui.quotes.quote_stream_controller import QuoteStreamController
from vnpy_ashare.ui.quotes.table_controller import TableController
from vnpy_ashare.ui.quotes.watchlist_controller import WatchlistController
from vnpy_ashare.ui.quotes.workers import (
    BarGapCheckWorker,
    BatchFillWorker,
    BatchGapFillWorker,
    BarsLoadWorker,
    DepthRefreshWorker,
    DiagnoseWorker,
    DownloadWorker,
    MinuteDownloadWorker,
    QuotesRefreshWorker,
)
from vnpy_ashare.models import StockItem
from vnpy_ashare.quotes.tickflow_stream import TickflowStreamBridge
from vnpy_ashare.ui.chart_panel import ChartPanel
from vnpy_ashare.ui.depth_panel import DepthPanel
from vnpy_ashare.ui.qt_helpers import release_thread
from vnpy_ashare.ui.diagnose_panel import DiagnosePanel
from vnpy_ashare.ui.quotes_config import (
    PAGE_CONFIGS,
    SEARCH_DEBOUNCE_MS,
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
        self._batch_backtest = WatchlistBatchBacktestController(self)
        self._loader = DataLoaderController(self)
        self._retired_workers: list[QtCore.QThread] = []
        self._load_generation = 0
        self._bars_generation = 0
        self._bars_request_id = 0
        self._active = False
        self._market_page = 0
        self._market_total = 0
        self._market_board: str | None = None
        self._apply_default_table_sort = False

        self._load_worker: QtCore.QThread | None = None
        self._market_worker: QtCore.QThread | None = None
        self._sync_worker: QtCore.QThread | None = None
        self._bars_worker: BarsLoadWorker | None = None
        self._download_worker: DownloadWorker | None = None
        self._batch_fill_worker: BatchFillWorker | None = None
        self._batch_gap_fill_worker: BatchGapFillWorker | None = None
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
        from vnpy_ashare.ui.quotes.page_shell import QuotesPageShell

        QuotesPageShell(self).build()

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
        self._update_quote_source_label()

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
            "_batch_fill_worker",
            "_batch_gap_fill_worker",
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

    def _refresh_market_clicked(self) -> None:
        self._loader.refresh_market_clicked()

    def load_market_page(self, *, quiet: bool = False) -> None:
        self._loader.load_market_page(quiet=quiet)

    def load_stock_list(self) -> None:
        self._loader.load_stock_list()

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

    def _emit_ai_context(self) -> None:
        self._actions.emit_ai_context()

    def _update_quote_source_label(self) -> None:
        from vnpy_ashare.quotes.provider import is_gateway_quote_active
        from vnpy_ashare.ui.quotes_config import quote_source_label

        label = getattr(self, "quote_source_label", None)
        if label is None:
            return
        text = quote_source_label(
            self.config,
            stream_active=self._use_quote_stream(),
            gateway_active=is_gateway_quote_active(),
        )
        label.setText(text)
        label.setVisible(bool(text))

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

    def _get_quote_service(self):
        from vnpy_ashare.engine_access import get_service

        return get_service(self._get_main_engine(), "quote_service")

    def run_watchlist_batch_backtest(self) -> None:
        self._batch_backtest.run_batch_backtest()

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
        self._loader.sync_universe_clicked()

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

    def batch_fill_stale(self) -> None:
        self._local.batch_fill_stale()

    def batch_fill_gaps(self) -> None:
        self._local.batch_fill_gaps()

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
            if self.config.show_batch_fill_button:
                self.batch_fill_button.setEnabled(False)
            if self.config.show_batch_gap_fill_button:
                self.batch_gap_fill_button.setEnabled(False)
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
