"""自选页工作流布局预设（盘中 / 登记 / 复盘）。"""

from __future__ import annotations

from vnpy_ashare.config.preferences.watchlist_position import save_position_panel_expanded
from vnpy_ashare.config.preferences.watchlist_signal import save_signal_panel_expanded
from vnpy_ashare.ui.quotes.features.watchlist.prefs import LayoutPresetId, save_watchlist_layout_preset
from vnpy_ashare.ui.quotes.features.watchlist.preset_specs import POSITION_FOCUS_TABLE_RATIO, PRESET_LABELS, PRESET_PANEL_STATE, PRESET_SPECS
from vnpy_ashare.ui.quotes.features.watchlist.toolbar_preset import apply_toolbar_for_preset
from vnpy_ashare.ui.quotes.watchlist.host import WatchlistHost
from vnpy_ashare.ui.quotes.watchlist_signals.splitter import apply_center_splitter_sizes

# 兼容旧测试
_PRESET_PANEL_STATE = PRESET_PANEL_STATE


def layout_preset_options() -> tuple[tuple[LayoutPresetId, str], ...]:
    return PRESET_LABELS


def _apply_group_tab(page: WatchlistHost, preset_id: LayoutPresetId) -> None:
    spec = PRESET_SPECS[preset_id]
    groups = page._watchlist_groups
    if groups is None:
        return
    if spec.select_all_group:
        groups.select_all_tab()


def _apply_view_mode(page: WatchlistHost, preset_id: LayoutPresetId) -> None:
    spec = PRESET_SPECS[preset_id]
    if not spec.force_table_view or not page.config.show_watchlist_multiview:
        return
    page._multiview.set_view_mode("table")


def apply_layout_preset(page: WatchlistHost, preset_id: LayoutPresetId, *, persist: bool = True) -> None:
    page._watchlist_table_ratio_override = None
    spec = PRESET_SPECS[preset_id]
    signal_panel = getattr(page, "signal_panel", None)
    if signal_panel is not None:
        signal_panel.set_expanded(spec.signal_expanded, emit=True)
        save_signal_panel_expanded(spec.signal_expanded)
    position_panel = getattr(page, "position_panel", None)
    if position_panel is not None:
        position_panel.set_expanded(spec.position_expanded, emit=True)
        save_position_panel_expanded(spec.position_expanded)
    _apply_group_tab(page, preset_id)
    _apply_view_mode(page, preset_id)
    apply_toolbar_for_preset(page, preset_id)
    if persist:
        save_watchlist_layout_preset(preset_id)
    apply_center_splitter_sizes(page)


def apply_position_focus(page: WatchlistHost) -> None:
    """持仓专注：折叠信号区、展开持仓区，主表缩至最小比例（不切换登记预设）。"""
    page._watchlist_table_ratio_override = POSITION_FOCUS_TABLE_RATIO
    signal_panel = getattr(page, "signal_panel", None)
    if signal_panel is not None:
        signal_panel.set_expanded(False, emit=True)
        save_signal_panel_expanded(False)
    position_panel = getattr(page, "position_panel", None)
    if position_panel is not None:
        position_panel.set_expanded(True, emit=True)
        save_position_panel_expanded(True)
    apply_center_splitter_sizes(page)
