"""行情列表页：市场 / 雷达 / 自选 / 本地 各自独立。"""

from __future__ import annotations

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
from vnpy_ashare.config.preferences.strategy_profile import (
    StrategyProfileId,
    apply_strategy_profile,
    bootstrap_strategy_profile,
    load_strategy_profile_id,
)
from vnpy_ashare.config.preferences.watchlist_position import WatchlistPositionConfig, load_watchlist_position_config
from vnpy_ashare.config.preferences.watchlist_signal import WatchlistSignalConfig
from vnpy_ashare.data.bar_health import (
    BarGapResult,
    BarHealthStatus,
    BarMeta,
)
from vnpy_ashare.domain.market.depth_snapshot import DepthSnapshot
from vnpy_ashare.domain.market.quote_snapshot import QuoteSnapshot
from vnpy_ashare.domain.symbols.stock import StockItem, canonical_vt_symbol
from vnpy_ashare.domain.trading.position import PositionSnapshot
from vnpy_ashare.domain.trading.signal_snapshot import SignalSnapshot
from vnpy_ashare.domain.trading.stock_continuation import StockContinuationSnapshot
from vnpy_ashare.integrations.tickflow.stream import TickflowStreamBridge
from vnpy_ashare.services.analysis import AnalysisService
from vnpy_ashare.services.note import NoteService
from vnpy_ashare.services.position import PositionService
from vnpy_ashare.services.watchlist import WatchlistService
from vnpy_ashare.ui.components.task_run_output_panel import TaskRunOutputPanel
from vnpy_ashare.ui.features.notes_center.open import show_notes_center_dialog
from vnpy_ashare.ui.quotes.chart.panel import ChartPanel
from vnpy_ashare.ui.quotes.chart.section import ChartSectionPanel, sync_chart_splitter_for_expansion
from vnpy_ashare.ui.quotes.controllers.actions import ActionsController
from vnpy_ashare.ui.quotes.controllers.batch_backtest import WatchlistBatchBacktestController
from vnpy_ashare.ui.quotes.controllers.data_loader import DataLoaderController
from vnpy_ashare.ui.quotes.controllers.local_data import LocalDataController
from vnpy_ashare.ui.quotes.controllers.pagination import MarketPaginationController
from vnpy_ashare.ui.quotes.controllers.quote_stream import QuoteStreamController
from vnpy_ashare.ui.quotes.controllers.table import TableController
from vnpy_ashare.ui.quotes.controllers.watchlist import WatchlistController
from vnpy_ashare.ui.quotes.features.market_rank import MarketRankFeature
from vnpy_ashare.ui.quotes.features.stock_notes import StockNotesFeature
from vnpy_ashare.ui.quotes.features.watchlist import WatchlistPageFeature
from vnpy_ashare.ui.quotes.features.watchlist_panels import WatchlistPanelsFeature
from vnpy_ashare.ui.quotes.page.config import (
    MARKET_AUTO_REFRESH_DEFAULT,
    MARKET_SCROLL_DEBOUNCE_MS,
    PAGE_CONFIGS,
    SEARCH_DEBOUNCE_MS,
)
from vnpy_ashare.ui.quotes.page.controller_attrs import QuotesPageControllerAttrs
from vnpy_ashare.ui.quotes.page.header_chips import (
    open_risk_settings_for_page,
    refresh_emotion_cycle_chip_for_page,
    refresh_risk_gate_chip_for_page,
)
from vnpy_ashare.ui.quotes.page.layout_persistence import (
    on_quotes_page_resize,
    restore_splitter,
    save_splitter,
    schedule_center_splitter_layout,
    splitter_settings_key,
)
from vnpy_ashare.ui.quotes.page.market_drilldown import (
    apply_pending_market_drilldown,
    clear_market_drilldown_filters,
    open_concept_drilldown,
    open_industry_drilldown,
    set_market_industry_filter,
)
from vnpy_ashare.ui.quotes.page.quote_refresh import (
    market_auto_refresh_enabled as page_market_auto_refresh_enabled,
    on_market_auto_refresh_toggled,
    quote_auto_refresh_enabled as page_quote_auto_refresh_enabled,
    quote_auto_refresh_paused_for_hours as page_quote_auto_refresh_paused_for_hours,
    schedule_quote_auto_refresh,
    update_quote_source_label,
    update_refresh_hint_label,
)
from vnpy_ashare.ui.quotes.page.session_lifecycle import activate_quotes_page, deactivate_quotes_page
from vnpy_ashare.ui.quotes.page.shell import QuotesPageShell
from vnpy_ashare.ui.quotes.page.shell_attrs import QuotesPageShellAttrs
from vnpy_ashare.ui.quotes.page.task_busy import (
    begin_cancellable_task,
    collect_busy_widgets,
    end_cancellable_task,
    finish_cancellable_task,
    set_busy,
)
from vnpy_ashare.ui.quotes.panels.depth import DepthPanel
from vnpy_ashare.ui.quotes.panels.diagnose import DiagnosePanel
from vnpy_ashare.ui.quotes.panels.loading_overlay import MarketTableHost
from vnpy_ashare.ui.quotes.radar.resonance_panel import sync_radar_resonance_splitter_for_expansion
from vnpy_ashare.ui.quotes.watchlist.bootstrap import WatchlistBootstrapCoordinator
from vnpy_ashare.ui.quotes.watchlist.refresh_scheduler import WatchlistStrategyRefreshScheduler
from vnpy_ashare.ui.quotes.watchlist.strategy_batch import WatchlistStrategyBatchCoordinator
from vnpy_ashare.ui.quotes.watchlist_groups.controller import WatchlistGroupController
from vnpy_ashare.ui.quotes.watchlist_multiview.controller import WatchlistMultiViewController
from vnpy_ashare.ui.quotes.watchlist_positions.controller import WatchlistPositionController
from vnpy_ashare.ui.quotes.watchlist_signals.controller import WatchlistSignalController
from vnpy_ashare.ui.quotes.workers.quotes_workers import (
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
from vnpy_common.ui.theme.manager import theme_manager


class QuotesPage(QuotesPageShellAttrs, QuotesPageControllerAttrs, QtWidgets.QWidget):
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
        self._strategy_refresh = WatchlistStrategyRefreshScheduler(self, self._signals, self._positions)
        self._strategy_batch = WatchlistStrategyBatchCoordinator(self) if page_name == "自选" else None
        self._watchlist_groups: WatchlistGroupController | None = None
        self._loader = DataLoaderController(self)
        self.signal_config: WatchlistSignalConfig = bootstrap_strategy_profile()
        self.position_config: WatchlistPositionConfig = load_watchlist_position_config()
        self.signal_cache: dict[str, SignalSnapshot] = {}
        self.continuation_cache: dict[str, StockContinuationSnapshot] = {}
        self.strategy_workspace_button: QtWidgets.QPushButton | None = None
        self._strategy_workspace_open = False
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
        self._watchlist_feature: WatchlistPageFeature | None = WatchlistPageFeature(self) if page_name == "自选" else None
        self._watchlist_bootstrap: WatchlistBootstrapCoordinator | None = WatchlistBootstrapCoordinator() if page_name == "自选" else None
        self._stock_notes = StockNotesFeature(self)
        self._market_auto_refresh = MARKET_AUTO_REFRESH_DEFAULT
        self._market_sort_column: str | None = None
        self._market_sort_ascending = True
        self._center_splitter_bound = False
        self.emotion_cycle_more_button: QtWidgets.QPushButton | None = None
        self.risk_gate_more_button: QtWidgets.QPushButton | None = None
        self._watchlist_table_ratio_override: float | None = None
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
        self._radar_resonance_splitter_saved_state: QtCore.QByteArray | None = None
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
        self.watchlist_pool_context_bar = None
        QuotesPageShell(self).build()
        if self.config.show_watchlist_groups:
            self._watchlist_groups = WatchlistGroupController(self)
            self._watchlist_groups.wire()
        if self._watchlist_feature is not None:
            self._watchlist_feature.wire()

    def activate(self) -> None:
        activate_quotes_page(self)

    def _refresh_emotion_cycle_chip(self) -> None:
        refresh_emotion_cycle_chip_for_page(self)

    def _refresh_risk_gate_chip(self) -> None:
        refresh_risk_gate_chip_for_page(self)

    def _open_risk_settings(self) -> None:
        open_risk_settings_for_page(self)

    def deactivate(self) -> None:
        deactivate_quotes_page(self)

    def _splitter_settings_key(self) -> str:
        return splitter_settings_key(self)

    def _column_settings_key(self) -> str:
        return self._table.column_settings_key()

    def _save_splitter(self) -> None:
        save_splitter(self)

    def _restore_splitter(self) -> None:
        restore_splitter(self)

    def _schedule_center_splitter_layout(self) -> None:
        schedule_center_splitter_layout(self)

    def showEvent(self, event: QtGui.QShowEvent) -> None:
        super().showEvent(event)
        schedule_center_splitter_layout(self)

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:
        super().resizeEvent(event)
        on_quotes_page_resize(self, event)

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
        set_market_industry_filter(self, industry)

    def clear_market_drilldown_filters(self) -> None:
        clear_market_drilldown_filters(self)

    def _apply_pending_market_drilldown(self) -> bool:
        return apply_pending_market_drilldown(self)

    def open_industry_drilldown(self, industry: str, *, rank_id: str = "net_mf_in") -> None:
        open_industry_drilldown(self, industry, rank_id=rank_id)

    def open_concept_drilldown(
        self,
        concept_name: str,
        vt_symbols: list[str],
        *,
        rank_id: str = "net_mf_in",
    ) -> None:
        open_concept_drilldown(self, concept_name, vt_symbols, rank_id=rank_id)

    def _render_table(self, *, preserve_selection: bool = True) -> None:
        self._table.render_table(preserve_selection=preserve_selection)

    def _update_stats(self) -> None:
        self._table.update_stats()

    def refresh_watchlist_signals(self) -> None:
        self._signals.invalidate_memory_cache()
        self._signals.refresh(force=True)

    def apply_strategy_profile(self, profile_id: str) -> None:

        typed_id = cast(StrategyProfileId, profile_id)
        from_profile_id = cast(StrategyProfileId, load_strategy_profile_id())
        if from_profile_id != typed_id:
            from vnpy_ashare.services.trading_playbook import (
                apply_playbook_template_merge,
                list_playbook_merge_candidate_sections,
                touch_playbook_seeded_profile,
            )
            from vnpy_ashare.ui.home.playbook_merge_dialog import prompt_playbook_template_merge

            candidates = list_playbook_merge_candidate_sections(from_profile_id, typed_id)
            self.signal_config = apply_strategy_profile(typed_id)
            if candidates and prompt_playbook_template_merge(
                self,
                from_profile_id=from_profile_id,
                to_profile_id=typed_id,
                section_ids=candidates,
            ):
                apply_playbook_template_merge(typed_id, candidates)
            else:
                touch_playbook_seeded_profile(typed_id)
        else:
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

    def _on_radar_resonance_expansion_changed(self, expanded: bool) -> None:
        sync_radar_resonance_splitter_for_expansion(self, expanded)

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

    def watchlist_pool_items(self) -> list[StockItem]:
        """自选全池（不受分组 Tab 筛选影响）。"""
        pool = self.watchlist_pool_stocks
        if pool:
            return list(pool)
        return list(self.all_stocks)

    def find_stock_item(self, vt_symbol: str) -> StockItem | None:
        target = (vt_symbol or "").strip()
        if not target:
            return None
        canon = canonical_vt_symbol(target)
        for item in self.watchlist_pool_items():
            if item.vt_symbol == target or (canon is not None and item.vt_symbol == canon):
                return item
        for item in self.all_stocks:
            if item.vt_symbol == target or (canon is not None and item.vt_symbol == canon):
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
        return page_market_auto_refresh_enabled(self)

    def market_uses_client_pagination(self) -> bool:
        return self.config.use_market_rank and self.config.market_full_list and self._market_catalog_loaded

    def apply_market_page_view(self) -> None:
        if self.market_uses_client_pagination():
            self._table.apply_market_display()
        else:
            self.load_market_page()

    def quote_auto_refresh_enabled(self) -> bool:
        return page_quote_auto_refresh_enabled(self)

    def quote_auto_refresh_paused_for_hours(self) -> bool:
        return page_quote_auto_refresh_paused_for_hours(self)

    def schedule_quote_auto_refresh(self) -> None:
        schedule_quote_auto_refresh(self)

    def _on_market_auto_refresh_toggled(self, checked: bool) -> None:
        on_market_auto_refresh_toggled(self, checked)

    def _update_refresh_hint_label(self) -> None:
        update_refresh_hint_label(self)

    def _update_quote_source_label(self) -> None:
        update_quote_source_label(self)

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
        return collect_busy_widgets(self, lock_table=lock_table)

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
        begin_cancellable_task(
            self,
            message,
            worker_attr=worker_attr,
            primary=primary,
            primary_text=primary_text,
            primary_handler=primary_handler,
            lock_table=lock_table,
        )

    def _end_cancellable_task(self) -> bool:
        return end_cancellable_task(self)

    def _finish_cancellable_task(self, *, cancelled_message: str = "任务已取消") -> bool:
        return finish_cancellable_task(self, cancelled_message=cancelled_message)

    def _set_busy(self, busy: bool, *, lock_table: bool = True) -> None:
        set_busy(self, busy, lock_table=lock_table)
