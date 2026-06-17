"""行情列表页：市场 / 雷达 / 自选 / 本地 各自独立。"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, cast

from vnpy.event import EventEngine
from vnpy.trader.constant import Exchange
from vnpy.trader.ui import QtCore, QtGui, QtWidgets

from vnpy_ashare.app.engine_access import (
    get_analysis_service,
    get_bar_service,
    get_note_service,
    get_position_service,
    get_quote_service,
    get_watchlist_service,
)
from vnpy_ashare.config.preferences import (
    WatchlistPositionConfig,
    load_watchlist_position_config,
)
from vnpy_ashare.config.preferences._settings import get_settings
from vnpy_ashare.config.preferences.strategy_profile import StrategyProfileId, apply_strategy_profile
from vnpy_ashare.data.bar_health import (
    BarGapResult,
    BarHealthStatus,
    BarMeta,
)
from vnpy_ashare.domain.symbols import StockItem
from vnpy_ashare.domain.time.market_hours import CHINA_TZ, is_ashare_trading_session, next_quotes_collect_at
from vnpy_ashare.domain.trading.position import PositionSnapshot
from vnpy_ashare.domain.trading.signal_snapshot import SignalSnapshot
from vnpy_ashare.integrations.tickflow import TickflowStreamBridge
from vnpy_ashare.quotes import QuoteSnapshot
from vnpy_ashare.domain.market.depth_snapshot import DepthSnapshot
from vnpy_ashare.quotes.core.provider import is_gateway_quote_active
from vnpy_ashare.quotes.rank.rank_catalog import get_rank_definition
from vnpy_ashare.services.analysis import AnalysisService
from vnpy_ashare.services.note import NoteService
from vnpy_ashare.services.position import PositionService
from vnpy_ashare.services.watchlist import WatchlistService
from vnpy_ashare.ui.components.task_run_output_panel import TaskRunOutputPanel
from vnpy_ashare.ui.features.notes_center import show_notes_center_dialog
from vnpy_ashare.ui.quotes.chart import ChartPanel, ChartSectionPanel
from vnpy_ashare.ui.quotes.chart.section import sync_chart_splitter_for_expansion
from vnpy_ashare.ui.quotes.controllers import (
    ActionsController,
    DataLoaderController,
    LocalDataController,
    MarketPaginationController,
    QuoteStreamController,
    TableController,
    WatchlistBatchBacktestController,
    WatchlistController,
)
from vnpy_ashare.ui.quotes.features import MarketRankFeature, StockNotesFeature, WatchlistPanelsFeature
from vnpy_ashare.ui.quotes.features.market_rank import SECTOR_DRILLDOWN_RANK_ID
from vnpy_ashare.ui.quotes.market_overview.emotion_cycle_refresh import refresh_emotion_cycle_chip
from vnpy_ashare.ui.quotes.page.config import (
    MARKET_AUTO_REFRESH_DEFAULT,
    MARKET_SCROLL_DEBOUNCE_MS,
    PAGE_CONFIGS,
    SEARCH_DEBOUNCE_MS,
    quote_refresh_hint,
    quote_refresh_seconds,
    quote_source_label,
    radar_refresh_hint,
    save_market_auto_refresh_pref,
)
from vnpy_ashare.ui.quotes.page.shell import QuotesPageShell
from vnpy_ashare.ui.quotes.page.shell_attrs import QuotesPageShellAttrs
from vnpy_ashare.ui.quotes.panels import DepthPanel, DiagnosePanel, MarketTableHost
from vnpy_ashare.ui.quotes.watchlist_groups import WatchlistGroupController
from vnpy_ashare.ui.quotes.watchlist_multiview import WatchlistMultiViewController
from vnpy_ashare.ui.quotes.watchlist_positions import WatchlistPositionController
from vnpy_ashare.ui.quotes.watchlist_signals import (
    WatchlistSignalConfig,
    WatchlistSignalController,
    apply_center_splitter_sizes,
    load_watchlist_signal_config,
    restore_center_splitter,
)
from vnpy_ashare.ui.quotes.workers import (
    BarGapCheckWorker,
    BarsLoadWorker,
    BatchFillWorker,
    BatchGapFillWorker,
    DepthRefreshWorker,
    DiagnoseWorker,
    DownloadWorker,
    InvalidBarCleanupWorker,
    MinuteDownloadWorker,
    QuotesRefreshWorker,
    ScopeBarsLoadWorker,
)
from vnpy_common.ui.feedback import TaskGuard
from vnpy_common.ui.qt_helpers import release_thread, thread_is_active
from vnpy_common.ui.theme import theme_manager


class QuotesPage(QuotesPageShellAttrs, QtWidgets.QWidget):
    """单页行情：列表 + 报价头 + 日 K。"""

    _thread_active = staticmethod(thread_is_active)

    def _wait_worker_release(self, attr: str, *, timeout_ms: int = 3000) -> None:
        worker = getattr(self, attr, None)
        if worker is None:
            return
        setattr(self, attr, None)
        release_thread(self._retired_workers, worker, timeout_ms=timeout_ms)

    def _release_worker(self, worker: QtCore.QThread | None) -> None:
        release_thread(self._retired_workers, worker, timeout_ms=0)

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
        self.watchlist_pool_stocks: list[StockItem] = []
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
        self._signals = WatchlistSignalController(self)
        self._positions = WatchlistPositionController(self)
        self._multiview = WatchlistMultiViewController(self)
        self._watchlist_groups: WatchlistGroupController | None = None
        self._loader = DataLoaderController(self)
        self.signal_config: WatchlistSignalConfig = load_watchlist_signal_config()
        self.position_config: WatchlistPositionConfig = load_watchlist_position_config()
        self.signal_cache: dict[str, SignalSnapshot] = {}
        self._signal_cache_config: WatchlistSignalConfig | None = None
        self.position_cache: dict[str, PositionSnapshot] = {}
        self._position_cache_config: WatchlistSignalConfig | None = None
        self._retired_workers: list[QtCore.QThread] = []
        self._load_generation = 0
        self._bars_generation = 0
        self._bars_request_id = 0
        self._active = False
        self._market_page = 0
        self._market_total = 0
        self._local_total = 0
        self._market_board: str | None = None
        self._market_rank_id: str = self.config.default_rank_id
        self._market_catalog: list = []
        self._market_catalog_quotes: dict = {}
        self._market_catalog_loaded = False
        self._market_full_load_quiet = True
        self._market_updated_at: str | None = None
        self._market_page_cache: dict = {}
        self._market_count_cache: dict = {}
        self._market_loading_more = False
        self._market_load_mode = "rank"
        self._market_scroll_blocked = False
        self._market_last_load_more_at = 0.0
        self._apply_default_table_sort = False
        self._market_table_host: MarketTableHost | None = None
        self._market_matched: list[StockItem] = []
        self._market_board_base: list[StockItem] | None = None
        self._market_board_base_key: str | None = None
        self._market_filter_keyword: str = ""
        self._local_filter_keyword: str = ""
        self._market_industry_filter: str | None = None
        self._market_vt_whitelist: frozenset[str] | None = None
        self._market_drilldown_label: str | None = None
        self._pending_industry_drilldown: str | None = None
        self._pending_concept_drilldown: frozenset[str] | None = None
        self._industry_map_cache: dict[str, str] | None = None
        self._market_board_map_cache: dict[str, str] | None = None
        self._market_industry_filter_listener = None
        self._market_rank = MarketRankFeature(self)
        self._watchlist_panels = WatchlistPanelsFeature(self)
        self._stock_notes = StockNotesFeature(self)
        self._market_auto_refresh = MARKET_AUTO_REFRESH_DEFAULT
        self._market_sort_column: str | None = None
        self._market_sort_ascending = True
        self._center_splitter_bound = False
        self.column_button = None
        self.rank_sidebar = None
        self.rank_list = None
        self.chart = None
        self.signal_panel = None
        self.position_panel = None
        self.multiview_board = None
        self.view_table_button = None
        self.view_multiview_button = None
        self._center_view_stack = None
        self.stock_note_panel = None
        self.refresh_radar_button = None
        self.radar_ai_button = None
        self.radar_board = None
        self.radar_resonance_panel = None
        self._radar_controller = None
        self._radar_splitter = None
        self._rank_splitter = None
        self._rank_splitter_filter = None

        self._load_worker: QtCore.QThread | None = None
        self._market_worker: QtCore.QThread | None = None
        self._prefetch_worker: QtCore.QThread | None = None
        self._sync_worker: QtCore.QThread | None = None
        self._bars_worker: BarsLoadWorker | ScopeBarsLoadWorker | None = None
        self._download_worker: DownloadWorker | MinuteDownloadWorker | None = None
        self._batch_fill_worker: BatchFillWorker | None = None
        self._batch_gap_fill_worker: BatchGapFillWorker | None = None
        self._gap_worker: BarGapCheckWorker | None = None
        self._gap_generation = 0
        self._quotes_worker: QuotesRefreshWorker | None = None
        self._depth_worker: DepthRefreshWorker | None = None
        self._diagnose_worker: DiagnoseWorker | None = None
        self._invalid_bar_cleanup_worker: InvalidBarCleanupWorker | None = None
        self._depth_generation = 0
        self._depth_permission_denied = False
        self.depth_panel: DepthPanel | None = None
        self.diagnose_panel: DiagnosePanel | None = None
        self.chart_panel: ChartPanel | None = None
        self.chart_section: ChartSectionPanel | None = None
        self.chart_hint: QtWidgets.QLabel | None = None
        self._right_panel_widget: QtWidgets.QWidget | None = None
        self._chart_splitter_saved_state: QtCore.QByteArray | None = None
        self.run_output_panel: TaskRunOutputPanel | None = None
        self._center_splitter: QtWidgets.QSplitter | None = None
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
        self._quote_timer.setSingleShot(True)
        self._quote_timer.timeout.connect(self.refresh_quotes)

        self._market_scroll_timer = QtCore.QTimer(self)
        self._market_scroll_timer.setSingleShot(True)
        self._market_scroll_timer.setInterval(MARKET_SCROLL_DEBOUNCE_MS)
        self._market_scroll_timer.timeout.connect(self._check_market_scroll_load)

        self._market_cache_sync_timer = QtCore.QTimer(self)
        self._market_cache_sync_timer.setSingleShot(True)
        self._market_cache_sync_timer.setInterval(400)
        self._market_cache_sync_timer.timeout.connect(self._loader.flush_market_cache_sync)

        self._init_ui()
        self._task_guard = TaskGuard(self._toast)
        self._task_lock_table = True
        self._active_worker_attr: str | None = None
        theme_manager().register_callback(self._on_theme_changed)

    def _on_theme_changed(self, _tokens) -> None:
        if not self._active:
            return
        self._refresh_table_quotes()
        self._table.update_stats()
        if self.current_item is not None:
            self._actions.update_quote_header(self.current_item)
        if self.depth_panel is not None:
            self.depth_panel.refresh_colors()
        if self.chart_panel is not None:
            self._actions.refresh_charts_only()

    def _init_columns(self) -> None:
        self._table.init_columns()

    def _build_visible_headers(self) -> list[str]:
        return self._table.build_visible_headers()

    def _init_ui(self) -> None:
        self.watchlist_group_tab_bar = None
        QuotesPageShell(self).build()
        if self.config.show_watchlist_groups:
            self._watchlist_groups = WatchlistGroupController(self)
            self._watchlist_groups.wire()

    def activate(self) -> None:
        self._active = True
        if self.config.column_configurable and self._table.sync_tail_columns_with_config():
            self._table.rebuild_table()
        if self.config.use_radar_cards:
            self._update_quote_source_label()
            self._refresh_emotion_cycle_chip()
            controller = getattr(self, "_radar_controller", None)
            if controller is not None:
                controller.activate()
            return
        if self.chart_panel is not None:
            self.chart_panel.set_active(True)
        if self.config.use_quote_stream:
            self._stream.start()
        if self.config.show_add_watchlist_button or self.page_name == "自选":
            self._watchlist.refresh_keys()
        if self._watchlist_groups is not None:
            self._watchlist_groups.refresh_groups()
        if self.config.use_local_table:
            self._local.schedule_invalid_bar_cleanup()
        if self.config.use_local_table and not self.config.use_local_pagination:
            self._local.refresh_meta()
        if self.current_item is not None and self.chart_panel is not None:
            quote = self.quote_map.get(self.current_item.tickflow_symbol)
            self.chart_panel.load_item(self.current_item, quote=quote)
        self.load_stock_list()
        self._restore_splitter()
        chart_section = getattr(self, "chart_section", None)
        if chart_section is not None:
            self._on_chart_section_expansion_changed(chart_section.is_expanded())
        self._schedule_center_splitter_layout()
        self._update_quote_source_label()
        if self.config.show_watchlist_signals:
            self._signals.start()
            # 信号区名单来自 QSettings，不依赖自选表加载完成；避免列表加载取消后信号永不刷新。
            self._signals.on_stock_list_loaded()
        if self.config.show_watchlist_positions:
            self._positions.start()
            self._positions.on_stock_list_loaded()
        if self.config.show_stock_notes:
            self._stock_notes.on_selection_item()
        if self.config.show_watchlist_multiview:
            self._multiview.restore_view_mode()
        self._refresh_emotion_cycle_chip()

    def _refresh_emotion_cycle_chip(self) -> None:
        chip = getattr(self, "emotion_cycle_chip", None)
        if chip is None:
            return

        refresh_emotion_cycle_chip(chip)

    def deactivate(self) -> None:
        if self.config.use_radar_cards:
            controller = getattr(self, "_radar_controller", None)
            if controller is not None:
                controller.deactivate()
            self._active = False
            return
        self._save_splitter()
        self._save_column_config()
        self._active = False
        self._load_generation += 1
        self._bars_generation += 1
        self._depth_generation += 1
        self._gap_generation += 1
        if self.chart_panel is not None:
            self.chart_panel.set_active(False)
        self._stream.stop()
        self._quote_timer.stop()
        self._signals.stop()
        self._positions.stop()
        panel = getattr(self, "stock_note_panel", None)
        if panel is not None:
            panel.flush_memo()
        for attr in (
            "_load_worker",
            "_market_worker",
            "_prefetch_worker",
            "_sync_worker",
            "_download_worker",
            "_batch_fill_worker",
            "_batch_gap_fill_worker",
        ):
            worker = getattr(self, attr, None)
            if worker is not None and hasattr(worker, "request_cancel"):
                worker.request_cancel()
        self._task_guard.end()
        self._set_busy(False, lock_table=self._task_lock_table)
        for attr in (
            "_load_worker",
            "_market_worker",
            "_prefetch_worker",
            "_sync_worker",
            "_bars_worker",
            "_download_worker",
            "_batch_fill_worker",
            "_batch_gap_fill_worker",
            "_gap_worker",
            "_quotes_worker",
            "_depth_worker",
            "_diagnose_worker",
            "_invalid_bar_cleanup_worker",
        ):
            self._wait_worker_release(attr, timeout_ms=0)
        self._batch_backtest.release_workers(self._retired_workers)

    def _splitter_settings_key(self) -> str:
        return f"quotes/splitter/{self.page_name}"

    def _column_settings_key(self) -> str:
        return self._table.column_settings_key()

    def _save_splitter(self) -> None:
        if self._splitter is None:
            return
        settings = get_settings()
        settings.setValue(self._splitter_settings_key(), self._splitter.saveState())

    def _restore_splitter(self) -> None:
        if self._splitter is None:
            return
        settings = get_settings()
        state = settings.value(self._splitter_settings_key())
        if state is not None:
            self._splitter.restoreState(state)

    def _schedule_center_splitter_layout(self) -> None:
        if not (self.config.show_watchlist_signals or self.config.show_watchlist_positions or self.config.show_run_output_panel):
            return
        QtCore.QTimer.singleShot(0, lambda: restore_center_splitter(self))
        QtCore.QTimer.singleShot(150, lambda: restore_center_splitter(self))

    def showEvent(self, event: QtGui.QShowEvent) -> None:
        super().showEvent(event)
        self._schedule_center_splitter_layout()

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:
        super().resizeEvent(event)
        if getattr(self, "_center_splitter", None) is not None:
            apply_center_splitter_sizes(self)

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

    def _load_rank_id_pref(self) -> str:
        return self._market_rank.load_rank_id_pref()

    def _save_rank_id_pref(self, rank_id: str) -> None:
        self._market_rank.save_rank_id_pref(rank_id)

    def _sync_rank_sort_from_catalog(self) -> None:
        self._market_rank.sync_sort_from_catalog()

    def _on_rank_item_clicked(self, item: QtWidgets.QListWidgetItem) -> None:
        self._market_rank.on_rank_item_clicked(item)

    def _init_rank_sidebar_selection(self) -> None:
        self._market_rank.init_sidebar_selection()

    def active_rank_title(self) -> str:
        return self._market_rank.active_rank_title()

    def _refresh_quotes_clicked(self) -> None:
        if self.config.use_market_rank:
            self._loader.refresh_market_clicked()
            return
        self._actions.refresh_quotes_manual()

    def _refresh_market_clicked(self) -> None:
        self._refresh_quotes_clicked()

    def load_market_page(self, *, quiet: bool = False, append: bool = False) -> None:
        self._loader.load_market_page(quiet=quiet, append=append)

    def _on_market_scroll(self, _value: int) -> None:
        if not self.config.market_scroll_paging or self._market_scroll_blocked:
            return
        self._market_scroll_timer.start()

    def _check_market_scroll_load(self) -> None:
        if not self.config.market_scroll_paging or self._market_scroll_blocked:
            return
        bar = self.market_table.verticalScrollBar()
        if bar.maximum() <= 0:
            return
        if bar.value() >= bar.maximum() - 120:
            self._loader.try_load_more_market()

    def _schedule_market_cache_sync(self) -> None:
        if self.config.use_market_rank:
            self._market_cache_sync_timer.start()

    def _market_quote_refresh_paused(self) -> bool:
        """滚动加载中暂停定时行情刷新，避免与追加渲染争抢主线程。"""
        return self._market_scroll_blocked or self._market_loading_more or self._market_scroll_timer.isActive() or self._thread_active(self._market_worker)

    def load_market_full(self, *, quiet: bool = False) -> None:
        self._loader.load_market_full(quiet=quiet)

    def _show_market_loading(self, text: str) -> None:
        host = self._market_table_host
        if host is not None:
            host.show_loading(text)

    def _hide_market_loading(self) -> None:
        host = self._market_table_host
        if host is not None:
            host.hide_loading()

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

    def set_market_industry_filter_listener(self, listener) -> None:
        self._market_industry_filter_listener = listener

    def set_market_industry_filter(self, industry: str | None) -> None:
        self._market_industry_filter = industry
        if industry:
            self._market_vt_whitelist = None
            self._market_drilldown_label = None
        listener = self._market_industry_filter_listener
        if listener is not None:
            listener(industry)
        self._table.filter_market_display()

    def clear_market_drilldown_filters(self) -> None:
        self._market_industry_filter = None
        self._market_vt_whitelist = None
        self._market_drilldown_label = None
        listener = self._market_industry_filter_listener
        if listener is not None:
            listener(None)
        self._table.filter_market_display()

    def open_industry_drilldown(self, industry: str, *, rank_id: str = "net_mf_in") -> None:
        """从板块资金等入口下钻：主力净流入榜 + 行业成分筛选。"""

        cleaned = str(industry or "").strip()
        if not cleaned:
            return
        self._pending_concept_drilldown = None
        target_rank = get_rank_definition(rank_id or SECTOR_DRILLDOWN_RANK_ID).id
        self._pending_industry_drilldown = cleaned
        self.search_edit.clear()
        self._market_filter_keyword = ""
        if self.config.use_market_rank:
            self._market_rank.apply_rank_for_drilldown(target_rank)
        else:
            self.set_market_industry_filter(cleaned)
            self._pending_industry_drilldown = None
        rank_title = get_rank_definition(target_rank).title
        self.status_label.setText(f"{rank_title} · 行业筛选：{cleaned}（来自板块资金，点击行业 × 可清除）")

    def open_concept_drilldown(
        self,
        concept_name: str,
        vt_symbols: list[str],
        *,
        rank_id: str = "net_mf_in",
    ) -> None:
        """从板块资金概念 Tab 下钻：主力净流入榜 + 概念成分白名单。"""

        label = str(concept_name or "").strip()
        cleaned = {str(item).strip() for item in vt_symbols if str(item or "").strip()}
        if not label or not cleaned:
            return
        self._pending_industry_drilldown = None
        target_rank = get_rank_definition(rank_id or SECTOR_DRILLDOWN_RANK_ID).id
        self._pending_concept_drilldown = frozenset(cleaned)
        self._market_drilldown_label = f"概念：{label}"
        self.search_edit.clear()
        self._market_filter_keyword = ""
        if self.config.use_market_rank:
            self._market_rank.apply_rank_for_drilldown(target_rank)
        else:
            self._market_vt_whitelist = self._pending_concept_drilldown
            self._pending_concept_drilldown = None
            self.set_market_industry_filter(None)
        rank_title = get_rank_definition(target_rank).title
        self.status_label.setText(f"{rank_title} · {self._market_drilldown_label}（来自板块资金）")

    def _render_table(self, *, preserve_selection: bool = True) -> None:
        self._table.render_table(preserve_selection=preserve_selection)

    def _update_stats(self) -> None:
        self._table.update_stats()

    def refresh_watchlist_signals(self) -> None:
        self._signals.invalidate_cache()
        self._signals.refresh(force=True)

    def apply_strategy_profile(self, profile_id: str) -> None:

        typed_id = cast(StrategyProfileId, profile_id)
        self.signal_config = apply_strategy_profile(typed_id)
        signal_panel = self.signal_panel
        if signal_panel is not None:
            signal_panel.apply_config(self.signal_config)
            signal_panel.sync_strategy_profile_combo(profile_id)
        position_panel = self.position_panel
        if position_panel is not None:
            position_panel.sync_strategy_profile_combo(profile_id)
        self.refresh_watchlist_signals()

    def refresh_watchlist_positions(self) -> None:
        self._positions.invalidate_cache()
        self._positions.refresh(force=True)

    def _wire_signal_panel(self) -> None:
        self._watchlist_panels.wire_signal_panel()

    def _wire_multiview(self) -> None:
        board = self.multiview_board
        if board is None:
            return
        self._multiview.wire_board(board)
        if self.view_table_button is not None:
            self.view_table_button.clicked.connect(lambda: self._multiview.set_view_mode("table"))
        if self.view_multiview_button is not None:
            self.view_multiview_button.clicked.connect(lambda: self._multiview.set_view_mode("multiview"))
        self._multiview.restore_view_mode()

    def _on_signal_panel_expansion_changed(self, expanded: bool) -> None:
        self._watchlist_panels.on_signal_panel_expansion_changed(expanded)

    def _on_chart_section_expansion_changed(self, expanded: bool) -> None:

        sync_chart_splitter_for_expansion(self, expanded)

    def _on_signal_panel_config_changed(self) -> None:
        self._watchlist_panels.on_signal_panel_config_changed()

    def apply_signal_panel_config(self) -> None:
        """应用信号区当前配置（构建 UI 期间也可安全调用）。"""
        self._watchlist_panels.apply_signal_panel_config()

    def _on_signal_panel_row_activated(self, vt_symbol: str) -> None:
        self._watchlist_panels.on_signal_panel_row_activated(vt_symbol)

    def _signal_chart_ref_kwargs(self) -> dict[str, int]:
        cfg = self.signal_config.normalized()
        return {"fast_window": cfg.fast_window, "slow_window": cfg.slow_window}

    def _wire_position_panel(self) -> None:
        self._watchlist_panels.wire_position_panel()

    def _wire_stock_note_panel(self) -> None:
        self._stock_notes.wire_panel()

    def quick_note_for_selected(self) -> None:
        self._stock_notes.focus_quick_note()

    def open_notes_center(self) -> None:

        main_engine = self._get_main_engine()
        if main_engine is None:
            return
        initial_vt_symbol = ""
        key = self._selected_stock_key()
        if key is not None:
            initial_vt_symbol = f"{key[0]}.{key[1].name}"
        parent = self.window()
        focus_watchlist = None
        if parent is not None and hasattr(parent, "focus_watchlist_symbol"):
            focus_watchlist = parent.focus_watchlist_symbol
        show_notes_center_dialog(
            main_engine,
            self.event_engine,
            focus_watchlist=focus_watchlist,
            initial_vt_symbol=initial_vt_symbol,
            parent=parent,
        )

    def _on_position_panel_expansion_changed(self, _expanded: bool) -> None:
        self._watchlist_panels.on_position_panel_expansion_changed(_expanded)

    def _on_position_panel_config_changed(self) -> None:
        self._watchlist_panels.on_position_panel_config_changed()

    def _apply_position_config(
        self,
        config: WatchlistPositionConfig,
        *,
        save: bool = True,
    ) -> None:
        self._watchlist_panels.apply_position_config(config, save=save)

    def _on_signal_register_position(self, vt_symbol: str) -> None:
        self._watchlist_panels.on_signal_register_position(vt_symbol)

    def _on_position_panel_row_selected(self, vt_symbol: str) -> None:
        self._watchlist_panels.on_position_panel_row_selected(vt_symbol)

    def _on_position_panel_row_activated(self, vt_symbol: str) -> None:
        self._watchlist_panels.on_position_panel_row_activated(vt_symbol)

    def register_position_for_selected(self) -> None:
        self._watchlist_panels.register_position_for_selected()

    def add_selection_to_signal_panel(self) -> None:
        self._watchlist_panels.add_selection_to_signal_panel()

    def find_stock_item(self, vt_symbol: str) -> StockItem | None:
        target = (vt_symbol or "").strip()
        if not target:
            return None
        for item in self.all_stocks:
            if item.vt_symbol == target:
                return item
        return None

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

    def market_auto_refresh_enabled(self) -> bool:
        if self.config.use_radar_cards:
            return False
        if self.config.use_market_rank:
            return self._market_auto_refresh
        return self.config.auto_refresh_quotes

    def market_uses_client_pagination(self) -> bool:
        return self.config.use_market_rank and self.config.market_full_list and self._market_catalog_loaded

    def apply_market_page_view(self) -> None:
        if self.market_uses_client_pagination():
            self._table.apply_market_display()
        else:
            self.load_market_page()

    def quote_auto_refresh_enabled(self) -> bool:
        if not self.config.quote_source:
            return False
        return self.market_auto_refresh_enabled()

    def quote_auto_refresh_paused_for_hours(self) -> bool:
        return self.quote_auto_refresh_enabled() and not is_ashare_trading_session()

    def schedule_quote_auto_refresh(self) -> None:
        """按交易时段调度下一次自动刷新（非交易时段休眠至下一段开盘）。"""
        if not self._active or not self.quote_auto_refresh_enabled():
            self._quote_timer.stop()
            self._update_refresh_hint_label()
            return

        now = datetime.now(CHINA_TZ)
        interval_sec = quote_refresh_seconds(self.config.quote_refresh_ms)
        next_at = next_quotes_collect_at(now, interval_seconds=interval_sec)
        delay_ms = max(int((next_at - now).total_seconds() * 1000), 1)
        self._quote_timer.setInterval(delay_ms)
        self._quote_timer.start()
        self._update_refresh_hint_label()

    def _on_market_auto_refresh_toggled(self, checked: bool) -> None:
        if self.config.use_radar_cards:
            return
        self._market_auto_refresh = checked
        save_market_auto_refresh_pref(checked)
        self._update_refresh_hint_label()
        self._market_page = 0
        self._market_page_cache.clear()
        self._pagination.set_visible()
        if checked:
            self._market_catalog_loaded = False
            self._market_full_load_quiet = True
            self.load_market_page()
            if is_ashare_trading_session():
                self.refresh_quotes()
            self.schedule_quote_auto_refresh()
        else:
            self._quote_timer.stop()
            if self._market_catalog_loaded:
                self._table.apply_market_display()
            else:
                self._market_full_load_quiet = True
                self.load_market_page()

    def _update_refresh_hint_label(self) -> None:
        label = getattr(self, "refresh_hint_label", None)
        if label is None:
            return
        if self.config.use_radar_cards:
            label.setText(radar_refresh_hint())
            return
        auto_refresh = self.quote_auto_refresh_enabled()
        label.setText(
            quote_refresh_hint(
                auto_refresh=auto_refresh,
                refresh_ms=self.config.quote_refresh_ms,
                quote_source=self.config.quote_source,
                paused_for_hours=self.quote_auto_refresh_paused_for_hours(),
            )
        )

    def _update_quote_source_label(self) -> None:
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
        if self.config.show_watchlist_multiview:
            self._multiview.on_chart_tab_changed(index)

    def _update_action_buttons(self) -> None:
        self._actions.update_action_buttons()

    def _get_main_engine(self):
        parent = self.parent()
        if parent is not None and hasattr(parent, "main_engine"):
            return parent.main_engine
        return None

    # ── Service 访问（统一经 engine_access，勿 getattr AshareEngine） ──

    def _get_watchlist_service(self) -> WatchlistService | None:
        return get_watchlist_service(self._get_main_engine())

    def _get_position_service(self) -> PositionService | None:
        return get_position_service(self._get_main_engine())

    def _get_note_service(self) -> NoteService | None:
        return get_note_service(self._get_main_engine())

    def _get_analysis_service(self) -> AnalysisService | None:
        return get_analysis_service(self._get_main_engine())

    def _get_quote_service(self):
        return get_quote_service(self._get_main_engine())

    def _get_bar_service(self):
        return get_bar_service(self._get_main_engine())

    def run_watchlist_batch_backtest(self) -> None:
        self._batch_backtest.run_batch_backtest()

    def run_diagnose_for_selected(self) -> None:
        self._actions.run_diagnose_for_selected()

    def _ask_ai_for_diagnose(self) -> None:
        self._actions.ask_ai_for_diagnose()

    def _ask_ai_for_team_analysis(self) -> None:
        self._actions.ask_ai_for_team_analysis()

    def _ask_ai_for_technical(self) -> None:
        self._actions.ask_ai_for_technical()

    def _ask_ai_for_signals(self) -> None:
        self._actions.ask_ai_for_signals()

    def _ask_ai_for_positions(self) -> None:
        self._actions.ask_ai_for_positions()

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
            row_count = self.quote_table_model.row_count()
            if row_count == 0:
                return
            current = table.currentIndex().row()
            if event.key() == QtCore.Qt.Key.Key_Up:
                next_row = current - 1 if current > 0 else 0
            else:
                next_row = current + 1 if current < row_count - 1 else row_count - 1
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
        mode: Literal["full", "incremental"] = "full",
        action_label: str = "下载",
    ) -> None:
        self._local.run_minute_download(mode=cast(Literal["full", "incremental"], mode), action_label=action_label)

    def fill_selected(self) -> None:
        self._local.fill_selected()

    def batch_fill_stale(self) -> None:
        self._local.batch_fill_stale()

    def batch_fill_gaps(self) -> None:
        self._local.batch_fill_gaps()

    def fill_selected_gaps(self) -> None:
        self._local.fill_selected_gaps()

    def redownload_selected(self) -> None:
        self._local.redownload_selected()

    def delete_selected_local(self) -> None:
        self._local.delete_selected()

    def _run_download(self, *, mode: Literal["full", "incremental"], action_label: str) -> None:
        self._local.run_download(mode=cast(Literal["full", "incremental"], mode), action_label=action_label)

    def _collect_busy_widgets(self, *, lock_table: bool = True) -> list[QtWidgets.QWidget]:
        widgets: list[QtWidgets.QWidget] = [self.search_edit]
        if self.config.use_local_table:
            widgets.append(self.local_period_combo)
        if self.config.show_board_filter:
            widgets.append(self.board_combo)
        if self.industry_filter is not None:
            widgets.append(self.industry_filter)
        if self.config.use_market_rank or self.config.show_refresh_quotes_button:
            widgets.append(self.refresh_quotes_button)
        if self.config.show_sync_button:
            widgets.append(self.sync_button)
        for name in (
            "download_button",
            "fill_button",
            "redownload_button",
            "delete_local_button",
            "batch_fill_button",
            "batch_gap_fill_button",
            "gap_fill_button",
            "add_watchlist_button",
            "remove_watchlist_button",
            "move_watchlist_up_button",
            "move_watchlist_down_button",
            "backtest_button",
            "batch_backtest_button",
            "diagnose_button",
        ):
            button = getattr(self, name, None)
            if button is not None:
                widgets.append(button)
        if lock_table and self.config.use_market_rank and not self.config.market_full_list:
            for name in (
                "home_button",
                "prev_page_button",
                "next_page_button",
                "end_button",
                "page_jump_input",
            ):
                control = getattr(self, name, None)
                if control is not None:
                    widgets.append(control)
        return widgets

    def _begin_cancellable_task(
        self,
        message: str,
        *,
        worker_attr: str,
        primary: QtWidgets.QPushButton | None = None,
        primary_text: str = "",
        primary_handler=None,
        lock_table: bool = True,
    ) -> None:
        self._active_worker_attr = worker_attr
        self._task_lock_table = lock_table
        self._set_busy(True, lock_table=lock_table)

        def on_cancel() -> None:
            worker = getattr(self, worker_attr, None)
            if worker is not None and hasattr(worker, "request_cancel"):
                worker.request_cancel()

        self._task_guard.begin(
            message,
            widgets=self._collect_busy_widgets(lock_table=lock_table),
            primary=primary,
            primary_text=primary_text,
            primary_handler=primary_handler,
            on_cancel=on_cancel,
        )

    def _end_cancellable_task(self) -> bool:
        cancelled = self._task_guard.cancelled
        self._task_guard.end()
        self._set_busy(False, lock_table=self._task_lock_table)
        self._active_worker_attr = None
        return cancelled

    def _finish_cancellable_task(self, *, cancelled_message: str = "任务已取消") -> bool:
        if self._end_cancellable_task():
            self._toast.info(cancelled_message)
            return True
        return False

    def _set_busy(self, busy: bool, *, lock_table: bool = True) -> None:
        self.search_edit.setEnabled(not busy)
        if self.config.use_local_table:
            self.local_period_combo.setEnabled(not busy)
        if self.config.show_board_filter:
            self.board_combo.setEnabled(not busy)
        if self.industry_filter is not None:
            self.industry_filter.setEnabled(not busy)
        rank_list = getattr(self, "rank_list", None)
        if rank_list is not None:
            rank_list.setEnabled(not busy)
        if self.config.use_market_rank or self.config.show_refresh_quotes_button:
            self.refresh_quotes_button.setEnabled(not busy)
        if self.config.show_sync_button:
            self.sync_button.setEnabled(not busy)
        if self.config.use_market_rank and not self.config.market_full_list:
            self._pagination.update_busy_state(busy)
        if busy:
            if self.config.show_download_button:
                self.download_button.setEnabled(False)
            if self.config.show_fill_button:
                self.fill_button.setEnabled(False)
            if self.config.show_redownload_button:
                self.redownload_button.setEnabled(False)
            if self.config.show_delete_button:
                self.delete_local_button.setEnabled(False)
            if self.config.show_batch_fill_button:
                self.batch_fill_button.setEnabled(False)
            if self.config.show_batch_gap_fill_button:
                self.batch_gap_fill_button.setEnabled(False)
                self.gap_fill_button.setEnabled(False)
            if self.config.show_add_watchlist_button:
                self.add_watchlist_button.setEnabled(False)
            if self.config.show_remove_watchlist_button:
                self.remove_watchlist_button.setEnabled(False)
            if self.config.show_watchlist_move_buttons:
                self.move_watchlist_up_button.setEnabled(False)
                self.move_watchlist_down_button.setEnabled(False)
        else:
            self._update_action_buttons()
        if lock_table:
            self.market_table.setEnabled(not busy)
