"""自选多维看盘控制器。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vnpy.trader.ui import QtCore

from vnpy_ashare.domain.time.market_hours import is_ashare_trading_session
from vnpy_ashare.quotes.watchlist_multiview.enrich import enrich_multiview_rows
from vnpy_ashare.quotes.watchlist_multiview.loader import build_watchlist_multiview_board_from_page
from vnpy_ashare.quotes.watchlist_multiview.summary import build_multiview_board_summary
from vnpy_ashare.quotes.watchlist_multiview.models import WatchlistMultiBoardData, WatchlistMultiSortKey
from vnpy_ashare.quotes.watchlist_multiview.sparkline_data import SparklineKind, SparklineMode
from vnpy_ashare.ui.features.stock_analysis.open import show_stock_analysis_from_quotes_page
from vnpy_ashare.ui.quotes.chart.tab_indices import DAILY_TAB_INDEX, MINUTE_TAB_INDEX
from vnpy_ashare.ui.quotes.watchlist_multiview.settings import (
    ViewMode,
    load_grid_columns,
    load_sort_key,
    load_view_mode,
    save_grid_columns,
    save_sort_key,
    save_view_mode,
)
from vnpy_ashare.ui.quotes.watchlist_multiview.worker import WatchlistMultiSparklineWorker
from vnpy_common.ui.qt_helpers import release_thread, thread_is_active

if TYPE_CHECKING:
    from vnpy_ashare.ui.quotes.page.quotes_page import QuotesPage
    from vnpy_ashare.ui.quotes.watchlist_multiview.panel import WatchlistMultiViewBoard

_SPARKLINE_REFRESH_MS = 60_000
_MULTIVIEW_QUOTE_DEBOUNCE_MS = 800


def _sparkline_mode_from_chart_tab(tab_index: int) -> SparklineMode:
    if tab_index == MINUTE_TAB_INDEX:
        return "minute"
    if tab_index == DAILY_TAB_INDEX:
        return "daily"
    return "intraday"


def _to_global_point(pos: object) -> QtCore.QPoint | None:
    if isinstance(pos, QtCore.QPoint):
        return pos
    if isinstance(pos, QtCore.QPointF):
        return pos.toPoint()
    return None


class WatchlistMultiViewController:
    """编排自选多维看盘刷新与选中联动。"""

    def __init__(self, page: QuotesPage) -> None:
        self._page = page
        self._sort_key: WatchlistMultiSortKey = load_sort_key()
        self._view_mode: ViewMode = load_view_mode()
        self._grid_columns = load_grid_columns()
        self._switching_view = False
        self._sparklines: dict[str, tuple[float, ...]] = {}
        self._sparkline_kind: SparklineKind = "none"
        self._sparkline_mode: SparklineMode = "intraday"
        self._sparkline_worker: WatchlistMultiSparklineWorker | None = None
        self._last_board: WatchlistMultiBoardData | None = None
        self._board_summary = ""
        self._sparkline_refresh_timer = QtCore.QTimer(page)
        self._sparkline_refresh_timer.setInterval(_SPARKLINE_REFRESH_MS)
        self._sparkline_refresh_timer.timeout.connect(self._on_sparkline_refresh_tick)
        self._quote_refresh_timer = QtCore.QTimer(page)
        self._quote_refresh_timer.setSingleShot(True)
        self._quote_refresh_timer.setInterval(_MULTIVIEW_QUOTE_DEBOUNCE_MS)
        self._quote_refresh_timer.timeout.connect(self._flush_quote_refresh)

    @property
    def view_mode(self) -> ViewMode:
        return self._view_mode

    @property
    def sort_key(self) -> WatchlistMultiSortKey:
        return self._sort_key

    @property
    def grid_columns(self) -> int:
        return self._grid_columns

    def board_summary_text(self) -> str:
        return self._board_summary

    def is_multiview_active(self) -> bool:
        return self._view_mode == "multiview"

    def wire_board(self, board: WatchlistMultiViewBoard) -> None:
        board.row_clicked.connect(self._on_row_clicked)
        board.row_double_clicked.connect(self._on_row_activated)
        board.row_context_menu_requested.connect(self._on_row_context_menu)
        board.sort_key_changed.connect(self.set_sort_key)
        board.grid_columns_changed.connect(self.set_grid_columns)
        board.apply_sort_key(self._sort_key)
        board.set_grid_columns(self._grid_columns)

    def set_view_mode(self, mode: ViewMode) -> None:
        if mode == self._view_mode:
            return
        self._view_mode = mode
        save_view_mode(mode)
        self._apply_view_mode()

    def set_sort_key(self, sort_key: WatchlistMultiSortKey) -> None:
        if sort_key == self._sort_key:
            return
        self._sort_key = sort_key
        save_sort_key(sort_key)
        board = getattr(self._page, "multiview_board", None)
        if board is not None:
            board.apply_sort_key(sort_key)
        if self.is_multiview_active():
            self.refresh(force=True, refresh_moneyflow=False)

    def set_grid_columns(self, columns: int) -> None:
        normalized = max(2, min(4, int(columns)))
        if normalized == self._grid_columns:
            return
        self._grid_columns = normalized
        save_grid_columns(normalized)
        board = getattr(self._page, "multiview_board", None)
        if board is not None:
            board.set_grid_columns(normalized)

    def restore_view_mode(self) -> None:
        self._view_mode = load_view_mode()
        self._grid_columns = load_grid_columns()
        board = getattr(self._page, "multiview_board", None)
        if board is not None:
            board.apply_sort_key(self._sort_key)
            board.set_grid_columns(self._grid_columns)
        self._sync_multiview_toolbar()
        self._apply_view_mode()

    def on_chart_tab_changed(self, tab_index: int) -> None:
        mode = _sparkline_mode_from_chart_tab(tab_index)
        if mode == self._sparkline_mode and self.is_multiview_active():
            self._sync_sparkline_refresh_timer()
            return
        self._sparkline_mode = mode
        if not self.is_multiview_active():
            return
        self._sparklines.clear()
        self._sparkline_kind = "none"
        self._schedule_sparkline_load(force=True)
        self._sync_sparkline_refresh_timer()

    def on_stock_list_loaded(self) -> None:
        self._sparklines.clear()
        self._sparkline_kind = "none"
        if self.is_multiview_active():
            self.refresh(force=True, refresh_moneyflow=True)
            self._schedule_sparkline_load()

    def on_bars_updated(self, vt_symbols: list[str] | None = None) -> None:
        if self._sparkline_mode == "intraday":
            return
        if vt_symbols:
            for vt_symbol in vt_symbols:
                self._sparklines.pop(vt_symbol, None)
        if self.is_multiview_active():
            self._schedule_sparkline_load(force=True)

    def on_quotes_updated(self) -> None:
        if not self.is_multiview_active():
            return
        self._quote_refresh_timer.start()

    def on_signal_or_position_updated(self) -> None:
        if self.is_multiview_active():
            self.refresh(force=False, refresh_moneyflow=False)

    def _flush_quote_refresh(self) -> None:
        if not self._page._active or not self.is_multiview_active():
            return
        self.refresh(force=False, refresh_moneyflow=False)

    def refresh(self, *, force: bool = False, refresh_moneyflow: bool | None = None) -> None:
        if refresh_moneyflow is None:
            refresh_moneyflow = force
        board = getattr(self._page, "multiview_board", None)
        if board is None or not self.is_multiview_active():
            return
        data = self._build_board_data(refresh_moneyflow=refresh_moneyflow)
        self._last_board = data
        board.apply_board(data)
        current = self._page.current_item
        if current is not None:
            board.highlight_symbol(current.vt_symbol)
        self._emit_ai_context_if_needed()

    def _build_board_data(self, *, refresh_moneyflow: bool = False) -> WatchlistMultiBoardData:
        page = self._page
        stocks = list(page.display_stocks) or list(page.all_stocks)
        base = build_watchlist_multiview_board_from_page(
            stocks=stocks,
            quote_map=page.quote_map,
            sort_key=self._sort_key,
            refresh_moneyflow=refresh_moneyflow,
        )
        signal_symbols = self._signal_symbols()
        rows = enrich_multiview_rows(
            base.rows,
            signal_symbols=signal_symbols,
            signal_cache=page.signal_cache,
            position_cache=page.position_cache,
            sparklines=self._sparklines,
            sparkline_kind=self._sparkline_kind,
        )
        data = WatchlistMultiBoardData(rows=rows, empty_message=base.empty_message, total_count=base.total_count)
        self._board_summary = build_multiview_board_summary(
            rows,
            signal_symbols=signal_symbols,
            signal_cache=page.signal_cache,
            position_cache=page.position_cache,
        )
        return data

    def _signal_symbols(self) -> set[str]:
        panel = getattr(self._page, "signal_panel", None)
        if panel is None or not panel.enabled:
            return set()
        return set(panel.symbols)

    def _schedule_sparkline_load(self, *, force: bool = False) -> None:
        page = self._page
        if not self.is_multiview_active() or not page.all_stocks:
            return
        if thread_is_active(self._sparkline_worker):
            if not force:
                return
            worker = self._sparkline_worker
            if worker is not None:
                worker.requestInterruption()
        worker = WatchlistMultiSparklineWorker(list(page.all_stocks), mode=self._sparkline_mode)
        self._sparkline_worker = worker

        def on_finished(payload: object) -> None:
            if self._sparkline_worker is worker:
                self._sparkline_worker = None
            try:
                if isinstance(payload, dict):
                    kind = payload.get("kind")
                    points = payload.get("points")
                    if kind in ("daily", "intraday", "minute", "none"):
                        self._sparkline_kind = kind
                    if isinstance(points, dict):
                        self._sparklines.update(points)
                if self.is_multiview_active():
                    self.refresh(force=False, refresh_moneyflow=False)
            finally:
                release_thread(page._retired_workers, worker, timeout_ms=0)

        def on_failed(_msg: str) -> None:
            if self._sparkline_worker is worker:
                self._sparkline_worker = None
            release_thread(page._retired_workers, worker, timeout_ms=0)

        worker.finished.connect(on_finished)
        worker.failed.connect(on_failed)
        worker.start()

    def _apply_view_mode(self) -> None:
        page = self._page
        stack = getattr(page, "_center_view_stack", None)
        if stack is None:
            return
        self._switching_view = True
        try:
            if self._view_mode == "multiview":
                self._sync_sparkline_mode_from_chart()
                stack.setCurrentWidget(page.multiview_board)
                self.refresh(force=True, refresh_moneyflow=True)
                self._schedule_sparkline_load()
                self._sync_sparkline_refresh_timer()
            else:
                stack.setCurrentWidget(page._market_table_host)
                self._quote_refresh_timer.stop()
                self._sparkline_refresh_timer.stop()
        finally:
            self._switching_view = False
        self._sync_multiview_toolbar()
        self._emit_ai_context_if_needed()

    def _sync_multiview_toolbar(self) -> None:
        page = self._page
        table_btn = getattr(page, "view_table_button", None)
        multiview_btn = getattr(page, "view_multiview_button", None)
        if table_btn is not None:
            table_btn.setChecked(self._view_mode == "table")
        if multiview_btn is not None:
            multiview_btn.setChecked(self._view_mode == "multiview")
        stats = page._stats_label
        if stats is not None:
            stats.setVisible(self._view_mode == "table" and page.config.column_configurable)

    def _sync_sparkline_mode_from_chart(self) -> None:
        panel = self._page.chart_panel
        if panel is not None:
            self._sparkline_mode = _sparkline_mode_from_chart_tab(panel.current_tab_index())

    def _sync_sparkline_refresh_timer(self) -> None:
        if not self.is_multiview_active() or not is_ashare_trading_session():
            self._sparkline_refresh_timer.stop()
            return
        if self._sparkline_mode in ("intraday", "minute"):
            self._sparkline_refresh_timer.start()
        else:
            self._sparkline_refresh_timer.stop()

    def _on_sparkline_refresh_tick(self) -> None:
        if not self.is_multiview_active() or not is_ashare_trading_session():
            self._sparkline_refresh_timer.stop()
            return
        if self._sparkline_mode not in ("intraday", "minute"):
            self._sparkline_refresh_timer.stop()
            return
        self._sparklines.clear()
        self._schedule_sparkline_load(force=True)

    def _emit_ai_context_if_needed(self) -> None:
        if self.is_multiview_active():
            self._page._actions.schedule_ai_context()

    def _on_row_clicked(self, vt_symbol: str) -> None:
        if self._switching_view:
            return
        item = self._page.find_stock_item(vt_symbol)
        if item is None:
            return
        self._page._select_stock_key((item.symbol, item.exchange))
        board = getattr(self._page, "multiview_board", None)
        if board is not None:
            board.highlight_symbol(vt_symbol)

    def _on_row_activated(self, vt_symbol: str) -> None:
        self._on_row_clicked(vt_symbol)
        item = self._page.find_stock_item(vt_symbol)
        if item is None:
            return

        quote = self._page.quote_map.get(item.tickflow_symbol)
        show_stock_analysis_from_quotes_page(item, self._page, quote=quote)

    def _on_row_context_menu(self, vt_symbol: str, global_pos: object) -> None:
        item = self._page.find_stock_item(vt_symbol)
        if item is None:
            return
        self._on_row_clicked(vt_symbol)
        popup_at = _to_global_point(global_pos)
        if popup_at is None:
            return
        self._page._actions.show_context_menu(QtCore.QPoint(), item=item, global_pos=popup_at)

    def on_table_selection_changed(self) -> None:
        if not self.is_multiview_active():
            return
        board = getattr(self._page, "multiview_board", None)
        current = self._page.current_item
        if board is None:
            return
        board.highlight_symbol(current.vt_symbol if current is not None else None)
