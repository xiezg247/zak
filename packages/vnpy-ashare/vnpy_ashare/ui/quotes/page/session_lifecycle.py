"""QuotesPage 激活 / 停用生命周期。"""

from __future__ import annotations

from typing import Any

from vnpy.trader.ui import QtCore

from vnpy_ashare.ui.quotes.page.header_chips import (
    refresh_emotion_cycle_chip_for_page,
)
from vnpy_ashare.ui.quotes.page.layout_persistence import (
    restore_center_splitter,
    schedule_save_layout,
)
from vnpy_ashare.ui.quotes.page.roles import STRATEGY_MONITOR_PAGE, WATCHLIST_PAGE
from vnpy_ashare.ui.quotes.page.worker_lifecycle import teardown_quotes_page_workers


def _strategy_stale_sweep_enabled(page: Any) -> bool:
    if page.page_name != STRATEGY_MONITOR_PAGE:
        return True
    signal_panel = getattr(page, "signal_panel", None)
    position_panel = getattr(page, "position_panel", None)
    signal_on = signal_panel is not None and signal_panel.enabled
    position_on = position_panel is not None and position_panel.enabled
    return signal_on or position_on


def _deferred_watchlist_activate(page: Any) -> None:
    """自选页延后任务：分组/图表/布局/多维看盘等，避免 Tab 切换卡死。"""
    if not page._active or page.page_name != WATCHLIST_PAGE:
        return
    lazy = getattr(page, "_watchlist_lazy", None)
    if lazy is not None:
        from vnpy_ashare.ui.quotes.watchlist_multiview.settings import load_view_mode

        lazy.ensure_for_activate(page, include_multiview=load_view_mode() == "multiview")
    if page._watchlist_groups is not None:
        page._watchlist_groups.refresh_groups()
    if page.current_item is not None and page.chart_panel is not None:
        quote = page.quote_map.get(page.current_item.tickflow_symbol)
        page.chart_panel.load_item(page.current_item, quote=quote)
    page._restore_splitter()
    chart_section = getattr(page, "chart_section", None)
    if chart_section is not None:
        page._on_chart_section_expansion_changed(chart_section.is_expanded())
    if page.config.show_stock_notes:
        page._stock_notes.on_selection_item()
    if page.config.show_watchlist_multiview:
        page._multiview.restore_view_mode()
    refresh_emotion_cycle_chip_for_page(page)
    if page._watchlist_feature is not None:
        page._watchlist_feature.on_activate()
    else:
        from vnpy_ashare.ui.quotes.onboarding.ultra_short import maybe_show_ultra_short_onboarding

        maybe_show_ultra_short_onboarding(page)
    page._update_quote_source_label()


def _deferred_strategy_monitor_activate(page: Any) -> None:
    if not page._active or page.page_name != STRATEGY_MONITOR_PAGE:
        return
    if page._watchlist_bootstrap is not None:
        page._watchlist_bootstrap.on_activate(page)
    else:
        pool = page._watchlist._pool_from_service()
        page.all_stocks = list(pool)
        page.display_stocks = list(pool)
        page._watchlist.refresh_keys()
    if page.config.show_watchlist_signals or page.config.show_watchlist_positions:
        if _strategy_stale_sweep_enabled(page):
            page._strategy_refresh.start()
        else:
            page._strategy_refresh.stop()
    page._signals.on_page_activated()
    feature = getattr(page, "_strategy_monitor_feature", None)
    if feature is not None:
        feature.on_activate()
    page._update_quote_source_label()
    if page.config.show_watchlist_signals or page.config.show_watchlist_positions:
        restore_center_splitter(page)


def activate_quotes_page(page: Any) -> None:
    page._active = True
    if page.config.use_radar_cards:
        if page.config.column_configurable and page._table.sync_tail_columns_with_config():
            page._table.rebuild_table()
        page._update_quote_source_label()
        refresh_emotion_cycle_chip_for_page(page)
        controller = getattr(page, "_radar_controller", None)
        if controller is not None:
            controller.activate()
        return

    if page.page_name == WATCHLIST_PAGE:
        if page.chart_panel is not None:
            page.chart_panel.set_active(True)
        if page.config.use_quote_stream:
            page._stream.resume()
        if page.config.column_configurable and page._table.sync_tail_columns_with_config():
            QtCore.QTimer.singleShot(0, page._table.rebuild_table)
        if page._watchlist_bootstrap is not None:
            page._watchlist_bootstrap.on_activate(page)
        else:
            pool = page._watchlist._pool_from_service()
            page.all_stocks = list(pool)
            page.apply_filter()
            page._watchlist.refresh_keys()
        page._strategy_refresh.stop()
        QtCore.QTimer.singleShot(0, lambda: _deferred_watchlist_activate(page))
        return

    if page.page_name == STRATEGY_MONITOR_PAGE:
        QtCore.QTimer.singleShot(0, lambda: _deferred_strategy_monitor_activate(page))
        return

    if page.config.column_configurable and page._table.sync_tail_columns_with_config():
        page._table.rebuild_table()
    if page.chart_panel is not None:
        page.chart_panel.set_active(True)
    if page.config.use_quote_stream:
        page._stream.start()
    if page.config.show_add_watchlist_button:
        page._watchlist.refresh_keys()
    if page._watchlist_groups is not None:
        page._watchlist_groups.refresh_groups()
    if page.config.use_local_table:
        page._local.schedule_invalid_bar_cleanup()
    if page.config.use_local_table and not page.config.use_local_pagination:
        page._local.refresh_meta()
    if page.current_item is not None and page.chart_panel is not None:
        quote = page.quote_map.get(page.current_item.tickflow_symbol)
        page.chart_panel.load_item(page.current_item, quote=quote)
    if page._watchlist_bootstrap is not None:
        page._watchlist_bootstrap.on_activate(page)
    else:
        page.load_stock_list()
    page._restore_splitter()
    chart_section = getattr(page, "chart_section", None)
    if chart_section is not None:
        page._on_chart_section_expansion_changed(chart_section.is_expanded())
    page._schedule_center_splitter_layout()
    page._update_quote_source_label()
    if page.config.show_watchlist_signals or page.config.show_watchlist_positions:
        page._strategy_refresh.start()
    page._signals.on_page_activated()
    if page.config.show_stock_notes:
        page._stock_notes.on_selection_item()
    if page.config.show_watchlist_multiview:
        page._multiview.restore_view_mode()
    refresh_emotion_cycle_chip_for_page(page)
    if page._watchlist_feature is not None:
        page._watchlist_feature.on_activate()


def deactivate_quotes_page(page: Any) -> None:
    if page.page_name in (WATCHLIST_PAGE, STRATEGY_MONITOR_PAGE) and hasattr(page, "end_tab_switch_loading"):
        page.end_tab_switch_loading()
    if page.config.use_radar_cards:
        controller = getattr(page, "_radar_controller", None)
        if controller is not None:
            controller.deactivate()
        page._active = False
        return
    schedule_save_layout(page)
    page._active = False
    page._load_generation += 1
    page._bars_generation += 1
    page._depth_generation += 1
    page._gap_generation += 1
    if page.chart_panel is not None:
        page.chart_panel.set_active(False)
    if page.config.use_quote_stream and page.page_name == WATCHLIST_PAGE:
        page._stream.pause()
    else:
        page._stream.stop()
    page._quote_timer.stop()
    page._strategy_refresh.stop()
    batch = getattr(page, "_strategy_batch", None)
    if batch is not None:
        batch.stop()
    page._signals.stop()
    page._positions.stop()
    panel = getattr(page, "stock_note_panel", None)
    if panel is not None:
        panel.flush_memo()
    teardown_quotes_page_workers(page)
