"""行情列表页：市场 / 雷达 / 自选 / 本地 各自独立。"""

from __future__ import annotations

from typing import Literal, cast

from vnpy.event import EventEngine
from vnpy.trader.constant import Exchange
from vnpy.trader.ui import QtCore, QtGui, QtWidgets

from vnpy_ashare.config.preferences.watchlist_position import WatchlistPositionConfig
from vnpy_ashare.domain.market.depth_snapshot import DepthSnapshot
from vnpy_ashare.domain.symbols.stock import StockItem
from vnpy_ashare.services.analysis import AnalysisService
from vnpy_ashare.services.note import NoteService
from vnpy_ashare.services.position import PositionService
from vnpy_ashare.services.watchlist import WatchlistService
from vnpy_ashare.ui.quotes.page.controller_attrs import QuotesPageControllerAttrs
from vnpy_ashare.ui.quotes.page.header_chips import refresh_emotion_cycle_chip_for_page
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
from vnpy_ashare.ui.quotes.page.page_bootstrap import (
    finish_page_init,
    init_controllers,
    init_page_config,
    init_page_state,
    init_timers,
    wire_page_features,
)
from vnpy_ashare.ui.quotes.page.panel_wiring import (
    add_selection_to_signal_panel,
    apply_position_config,
    apply_signal_panel_config,
    apply_strategy_profile_for_page,
    find_stock_item,
    on_chart_section_expansion_changed,
    on_position_panel_config_changed,
    on_position_panel_expansion_changed,
    on_position_panel_row_activated,
    on_position_panel_row_selected,
    on_radar_resonance_expansion_changed,
    on_signal_panel_config_changed,
    on_signal_panel_expansion_changed,
    on_signal_panel_row_activated,
    open_notes_center,
    refresh_watchlist_positions,
    refresh_watchlist_signals,
    signal_chart_ref_kwargs,
    watchlist_pool_items,
    wire_multiview,
    wire_position_panel,
    wire_signal_panel,
    wire_stock_note_panel,
)
from vnpy_ashare.ui.quotes.page.quote_refresh import (
    market_auto_refresh_enabled as page_market_auto_refresh_enabled,
)
from vnpy_ashare.ui.quotes.page.quote_refresh import (
    on_market_auto_refresh_toggled,
    schedule_quote_auto_refresh,
    update_quote_source_label,
    update_refresh_hint_label,
)
from vnpy_ashare.ui.quotes.page.quote_refresh import (
    quote_auto_refresh_enabled as page_quote_auto_refresh_enabled,
)
from vnpy_ashare.ui.quotes.page.quote_refresh import (
    quote_auto_refresh_paused_for_hours as page_quote_auto_refresh_paused_for_hours,
)
from vnpy_ashare.ui.quotes.page.roles import RADAR_PAGE, STRATEGY_MONITOR_PAGE, WATCHLIST_PAGE
from vnpy_ashare.ui.quotes.page.service_access import (
    get_analysis_service_for_page,
    get_bar_service_for_page,
    get_main_engine_for_page,
    get_note_service_for_page,
    get_position_service_for_page,
    get_quote_service_for_page,
    get_watchlist_service_for_page,
)
from vnpy_ashare.ui.quotes.page.session_lifecycle import activate_quotes_page, deactivate_quotes_page
from vnpy_ashare.ui.quotes.page.shell import QuotesPageShell
from vnpy_ashare.ui.quotes.page.shell_attrs import QuotesPageShellAttrs
from vnpy_ashare.ui.quotes.page.state_attrs import QuotesPageStateAttrs
from vnpy_ashare.ui.quotes.page.task_busy import (
    begin_cancellable_task,
    collect_busy_widgets,
    end_cancellable_task,
    finish_cancellable_task,
    set_busy,
)
from vnpy_ashare.ui.quotes.page.worker_lifecycle import release_worker, wait_worker_release
from vnpy_common.ui.loading_overlay import ContentLoadingOverlay
from vnpy_common.ui.qt_helpers import thread_is_active


class QuotesPage(QuotesPageShellAttrs, QuotesPageControllerAttrs, QuotesPageStateAttrs, QtWidgets.QWidget):
    """单页行情：列表 + 报价头 + 日 K。"""

    _thread_active = staticmethod(thread_is_active)

    def _wait_worker_release(self, attr: str, *, timeout_ms: int = 3000) -> None:
        wait_worker_release(self, attr, timeout_ms=timeout_ms)

    def _release_worker(self, worker: QtCore.QThread | None) -> None:
        release_worker(self, worker)

    def __init__(
        self,
        page_name: str,
        parent: QtWidgets.QWidget | None = None,
        *,
        event_engine: EventEngine | None = None,
    ) -> None:
        super().__init__(parent)
        init_page_config(self, page_name, event_engine=event_engine)
        init_page_state(self)
        init_controllers(self, page_name)
        init_timers(self)
        self._init_ui()
        finish_page_init(self)

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
        wire_page_features(self)

    def activate(self) -> None:
        activate_quotes_page(self)

    def _refresh_emotion_cycle_chip(self) -> None:
        refresh_emotion_cycle_chip_for_page(self)

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
        if not self.config.use_market_rank or self._market_background_sync_paused():
            return
        self._market_cache_sync_timer.start()

    def _market_quote_refresh_paused(self) -> bool:
        """滚动加载中暂停定时行情刷新，避免与追加渲染争抢主线程。"""
        return (
            self._market_scroll_blocked
            or self._market_loading_more
            or self._market_scroll_timer.isActive()
            or self._thread_active(self._market_worker)
            or self._thread_active(self._quotes_worker)
        )

    def load_market_full(self, *, quiet: bool = False) -> None:
        self._loader.load_market_full(quiet=quiet)

    def _tab_switch_loading_host(self) -> QtWidgets.QWidget | None:
        if self._market_table_host is not None:
            return self._market_table_host
        board = getattr(self, "radar_board", None)
        if board is not None:
            return board
        return getattr(self, "_center_splitter", None)

    def _ensure_tab_switch_loading_overlay(self, host: QtWidgets.QWidget) -> ContentLoadingOverlay:
        overlay = getattr(self, "_tab_switch_loading_overlay", None)
        if overlay is None or overlay.parentWidget() is not host:
            overlay = ContentLoadingOverlay(host)
            self._tab_switch_loading_overlay = overlay
        return overlay

    def _show_market_loading(self, text: str) -> None:
        host = self._market_table_host
        if host is not None:
            host.show_loading(text)

    def _hide_market_loading(self) -> None:
        host = self._market_table_host
        if host is not None:
            host.hide_loading()

    def _show_tab_switch_loading(self, text: str) -> None:
        host = self._tab_switch_loading_host()
        if host is None:
            return
        if host is self._market_table_host:
            host.show_loading(text)
            return
        self._ensure_tab_switch_loading_overlay(host).show_loading(text)

    def _hide_tab_switch_loading(self) -> None:
        host = self._tab_switch_loading_host()
        if host is self._market_table_host:
            host.hide_loading()
            return
        overlay = getattr(self, "_tab_switch_loading_overlay", None)
        if overlay is not None:
            overlay.hide_loading()

    def begin_tab_switch_loading(self) -> None:
        if self.page_name == RADAR_PAGE:
            self._tab_switch_loading = True
            self._show_tab_switch_loading("正在加载雷达…")
            return
        if self.page_name not in (WATCHLIST_PAGE, STRATEGY_MONITOR_PAGE):
            return
        self._tab_switch_loading = True
        text = "正在加载自选…" if self.page_name == WATCHLIST_PAGE else "正在加载策略监控…"
        self._show_tab_switch_loading(text)

    def end_tab_switch_loading(self) -> None:
        if not getattr(self, "_tab_switch_loading", False):
            return
        self._tab_switch_loading = False
        self._hide_tab_switch_loading()

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
        refresh_watchlist_signals(self)

    def apply_strategy_profile(self, profile_id: str) -> None:
        apply_strategy_profile_for_page(self, profile_id)

    def refresh_watchlist_positions(self) -> None:
        refresh_watchlist_positions(self)

    def _wire_signal_panel(self) -> None:
        wire_signal_panel(self)

    def _wire_multiview(self) -> None:
        wire_multiview(self)

    def _on_signal_panel_expansion_changed(self, expanded: bool) -> None:
        on_signal_panel_expansion_changed(self, expanded)

    def _on_chart_section_expansion_changed(self, expanded: bool) -> None:
        on_chart_section_expansion_changed(self, expanded)

    def _on_radar_resonance_expansion_changed(self, expanded: bool) -> None:
        on_radar_resonance_expansion_changed(self, expanded)

    def _on_signal_panel_config_changed(self) -> None:
        on_signal_panel_config_changed(self)

    def apply_signal_panel_config(self) -> None:
        apply_signal_panel_config(self)

    def _on_signal_panel_row_activated(self, vt_symbol: str) -> None:
        on_signal_panel_row_activated(self, vt_symbol)

    def _signal_chart_ref_kwargs(self) -> dict[str, int]:
        return signal_chart_ref_kwargs(self)

    def _wire_position_panel(self) -> None:
        wire_position_panel(self)

    def _wire_stock_note_panel(self) -> None:
        wire_stock_note_panel(self)

    def quick_note_for_selected(self) -> None:
        self._stock_notes.focus_quick_note()

    def open_notes_center(self) -> None:
        open_notes_center(self)

    def _on_position_panel_expansion_changed(self, _expanded: bool) -> None:
        on_position_panel_expansion_changed(self, _expanded)

    def _on_position_panel_config_changed(self) -> None:
        on_position_panel_config_changed(self)

    def _apply_position_config(
        self,
        config: WatchlistPositionConfig,
        *,
        save: bool = True,
    ) -> None:
        apply_position_config(self, config, save=save)

    def _on_position_panel_row_selected(self, vt_symbol: str) -> None:
        on_position_panel_row_selected(self, vt_symbol)

    def _on_position_panel_row_activated(self, vt_symbol: str) -> None:
        on_position_panel_row_activated(self, vt_symbol)

    def add_selection_to_signal_panel(self) -> None:
        add_selection_to_signal_panel(self)

    def watchlist_pool_items(self) -> list[StockItem]:
        return watchlist_pool_items(self)

    def find_stock_item(self, vt_symbol: str) -> StockItem | None:
        return find_stock_item(self, vt_symbol)

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
        return get_main_engine_for_page(self)

    def _get_watchlist_service(self) -> WatchlistService | None:
        return get_watchlist_service_for_page(self)

    def _get_position_service(self) -> PositionService | None:
        return get_position_service_for_page(self)

    def _get_note_service(self) -> NoteService | None:
        return get_note_service_for_page(self)

    def _get_analysis_service(self) -> AnalysisService | None:
        return get_analysis_service_for_page(self)

    def _get_quote_service(self):
        return get_quote_service_for_page(self)

    def _get_bar_service(self):
        return get_bar_service_for_page(self)

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

    def remove_from_watchlist(self, item: StockItem | None = None) -> None:
        self._watchlist.remove_items(item)

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

    def _collect_busy_widgets(
        self,
        *,
        lock_table: bool = True,
        lock_search: bool = True,
    ) -> list[QtWidgets.QWidget]:
        return collect_busy_widgets(self, lock_table=lock_table, lock_search=lock_search)

    def _begin_cancellable_task(
        self,
        message: str,
        *,
        worker_attr: str,
        primary: QtWidgets.QPushButton | None = None,
        primary_text: str = "",
        primary_handler=None,
        lock_table: bool = True,
        lock_search: bool = True,
    ) -> None:
        begin_cancellable_task(
            self,
            message,
            worker_attr=worker_attr,
            primary=primary,
            primary_text=primary_text,
            primary_handler=primary_handler,
            lock_table=lock_table,
            lock_search=lock_search,
        )

    def _end_cancellable_task(self) -> bool:
        return end_cancellable_task(self)

    def _finish_cancellable_task(self, *, cancelled_message: str = "任务已取消") -> bool:
        return finish_cancellable_task(self, cancelled_message=cancelled_message)

    def _set_busy(
        self,
        busy: bool,
        *,
        lock_table: bool = True,
        lock_search: bool = True,
    ) -> None:
        set_busy(self, busy, lock_table=lock_table, lock_search=lock_search)

    def _market_background_sync_paused(self) -> bool:
        """滚动分页加载或与行情刷新争抢主线程时，延后缓存同步。"""
        return self._market_quote_refresh_paused()

    def _defer_when_market_idle(
        self,
        callback,
        *,
        retry_ms: int = 150,
        attempt: int = 0,
        max_attempts: int = 25,
    ) -> None:
        """市场页滚动/加载期间延后 UI 更新，避免与 append 渲染争抢。"""
        if not self.config.market_scroll_paging or not self._market_background_sync_paused() or attempt >= max_attempts:
            callback()
            return

        def _retry() -> None:
            QuotesPage._defer_when_market_idle(
                self,
                callback,
                retry_ms=retry_ms,
                attempt=attempt + 1,
                max_attempts=max_attempts,
            )

        QtCore.QTimer.singleShot(retry_ms, _retry)
