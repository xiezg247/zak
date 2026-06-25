"""QuotesPage 自选策略面板与多视图 wiring。"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from vnpy_ashare.config.preferences.strategy_profile import (
    StrategyProfileId,
    apply_strategy_profile,
    load_strategy_profile_id,
)
from vnpy_ashare.config.preferences.watchlist_position import WatchlistPositionConfig
from vnpy_ashare.domain.symbols.stock import StockItem, canonical_vt_symbol
from vnpy_ashare.ui.features.notes_center.open import show_notes_center_dialog
from vnpy_ashare.ui.quotes.chart.section import sync_chart_splitter_for_expansion
from vnpy_ashare.ui.quotes.radar.resonance_panel import sync_radar_resonance_splitter_for_expansion

if TYPE_CHECKING:
    from vnpy_ashare.ui.quotes.page.quotes_page import QuotesPage


def watchlist_pool_items(page: QuotesPage) -> list[StockItem]:
    """自选全池（不受分组 Tab 筛选影响）。"""
    pool = page.watchlist_pool_stocks
    if pool:
        return list(pool)
    return list(page.all_stocks)


def find_stock_item(page: QuotesPage, vt_symbol: str) -> StockItem | None:
    target = (vt_symbol or "").strip()
    if not target:
        return None
    canon = canonical_vt_symbol(target)
    for item in watchlist_pool_items(page):
        if item.vt_symbol == target or (canon is not None and item.vt_symbol == canon):
            return item
    for item in page.all_stocks:
        if item.vt_symbol == target or (canon is not None and item.vt_symbol == canon):
            return item
    return None


def apply_strategy_profile_for_page(page: QuotesPage, profile_id: str) -> None:
    typed_id = cast(StrategyProfileId, profile_id)
    from_profile_id = cast(StrategyProfileId, load_strategy_profile_id())
    page.signal_config = apply_strategy_profile(typed_id)
    if from_profile_id != typed_id:
        from vnpy_ashare.services.trading_playbook import sync_playbook_from_template

        sync_playbook_from_template(typed_id)
    signal_panel = page.signal_panel
    if signal_panel is not None:
        signal_panel.apply_config(page.signal_config)
        signal_panel.sync_strategy_profile_combo(profile_id)
    position_panel = page.position_panel
    if position_panel is not None:
        position_panel.sync_strategy_profile_combo(profile_id)
    refresh_watchlist_signals(page)


def refresh_watchlist_signals(page: QuotesPage) -> None:
    page._signals.invalidate_memory_cache()
    page._signals.refresh(force=True)


def refresh_watchlist_positions(page: QuotesPage) -> None:
    page._positions.invalidate_cache()
    page._positions.refresh(force=True)


def wire_signal_panel(page: QuotesPage) -> None:
    page._watchlist_panels.wire_signal_panel()


def wire_multiview(page: QuotesPage) -> None:
    board = page.multiview_board
    if board is None:
        return
    page._multiview.wire_board(board)
    if page.view_table_button is not None:
        page.view_table_button.clicked.connect(lambda: page._multiview.set_view_mode("table"))
    if page.view_multiview_button is not None:
        page.view_multiview_button.clicked.connect(lambda: page._multiview.set_view_mode("multiview"))
    page._multiview.restore_view_mode()


def wire_position_panel(page: QuotesPage) -> None:
    page._watchlist_panels.wire_position_panel()


def wire_stock_note_panel(page: QuotesPage) -> None:
    page._stock_notes.wire_panel()


def on_signal_panel_expansion_changed(page: QuotesPage, expanded: bool) -> None:
    page._watchlist_panels.on_signal_panel_expansion_changed(expanded)


def on_chart_section_expansion_changed(page: QuotesPage, expanded: bool) -> None:
    sync_chart_splitter_for_expansion(page, expanded)


def on_radar_resonance_expansion_changed(page: QuotesPage, expanded: bool) -> None:
    sync_radar_resonance_splitter_for_expansion(page, expanded)


def on_signal_panel_config_changed(page: QuotesPage) -> None:
    page._watchlist_panels.on_signal_panel_config_changed()


def apply_signal_panel_config(page: QuotesPage) -> None:
    """应用信号区当前配置（构建 UI 期间也可安全调用）。"""
    page._watchlist_panels.apply_signal_panel_config()


def on_signal_panel_row_activated(page: QuotesPage, vt_symbol: str) -> None:
    page._watchlist_panels.on_signal_panel_row_activated(vt_symbol)


def signal_chart_ref_kwargs(page: QuotesPage) -> dict[str, int]:
    cfg = page.signal_config.normalized()
    return {"fast_window": cfg.fast_window, "slow_window": cfg.slow_window}


def on_position_panel_expansion_changed(page: QuotesPage, _expanded: bool) -> None:
    page._watchlist_panels.on_position_panel_expansion_changed(_expanded)


def on_position_panel_config_changed(page: QuotesPage) -> None:
    page._watchlist_panels.on_position_panel_config_changed()


def apply_position_config(
    page: QuotesPage,
    config: WatchlistPositionConfig,
    *,
    save: bool = True,
) -> None:
    page._watchlist_panels.apply_position_config(config, save=save)


def on_position_panel_row_selected(page: QuotesPage, vt_symbol: str) -> None:
    page._watchlist_panels.on_position_panel_row_selected(vt_symbol)


def on_position_panel_row_activated(page: QuotesPage, vt_symbol: str) -> None:
    page._watchlist_panels.on_position_panel_row_activated(vt_symbol)


def add_selection_to_signal_panel(page: QuotesPage) -> None:
    page._watchlist_panels.add_selection_to_signal_panel()


def open_notes_center(page: QuotesPage) -> None:
    from vnpy_ashare.ui.quotes.page.service_access import get_main_engine_for_page

    main_engine = get_main_engine_for_page(page)
    if main_engine is None:
        return
    initial_vt_symbol = ""
    key = page._selected_stock_key()
    if key is not None:
        initial_vt_symbol = f"{key[0]}.{key[1].name}"
    parent = page.window()
    focus_watchlist = None
    if parent is not None and hasattr(parent, "focus_watchlist_symbol"):
        focus_watchlist = parent.focus_watchlist_symbol
    show_notes_center_dialog(
        main_engine,
        page.event_engine,
        focus_watchlist=focus_watchlist,
        initial_vt_symbol=initial_vt_symbol,
        parent=parent,
    )
