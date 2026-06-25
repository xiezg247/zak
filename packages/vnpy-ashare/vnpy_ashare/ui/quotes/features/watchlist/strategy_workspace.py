"""自选页策略/持仓工作区：工具栏主控、面板显隐与次要动作收拢。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.config.preferences.watchlist_position import save_position_panel_expanded
from vnpy_ashare.config.preferences.watchlist_signal import save_signal_panel_expanded
from vnpy_ashare.ui.quotes._host_widget import as_qwidget
from vnpy_ashare.ui.quotes.features.watchlist.prefs import LayoutPresetId, load_watchlist_layout_preset
from vnpy_ashare.ui.quotes.features.watchlist.preset_specs import PRESET_SPECS
from vnpy_ashare.ui.quotes.features.watchlist.strategy_workspace_prefs import (
    load_strategy_workspace_open,
    save_strategy_workspace_open,
)
from vnpy_ashare.ui.quotes.features.watchlist.toolbar_preset import apply_toolbar_for_preset
from vnpy_ashare.ui.quotes.watchlist.host import WatchlistHost
from vnpy_ashare.ui.quotes.watchlist_signals.splitter import apply_center_splitter_sizes

__all__ = [
    "append_strategy_workspace_more_actions",
    "apply_strategy_workspace",
    "create_strategy_workspace_toolbar",
    "format_strategy_workspace_button_label",
    "init_strategy_workspace_on_layout",
    "is_strategy_workspace_open",
    "open_strategy_workspace",
    "refresh_strategy_workspace_button",
    "set_strategy_panels_visible",
    "sync_strategy_workspace_from_preset",
]


def format_strategy_workspace_button_label(
    *,
    signal_count: int,
    position_count: int,
) -> str:
    return f"策略/持仓 · 信号 {signal_count} · 持仓 {position_count}"


def is_strategy_workspace_open(page: WatchlistHost) -> bool:
    cached = getattr(page, "_strategy_workspace_open", None)
    if isinstance(cached, bool):
        return cached
    return load_strategy_workspace_open()


def _signal_count(page: WatchlistHost) -> int:
    signal_panel = getattr(page, "signal_panel", None)
    if signal_panel is None:
        return 0
    return len(signal_panel.symbols)


def set_strategy_panels_visible(page: WatchlistHost, visible: bool) -> None:
    signal_panel = getattr(page, "signal_panel", None)
    if signal_panel is not None:
        signal_panel.setVisible(visible)
    position_panel = getattr(page, "position_panel", None)
    if position_panel is not None:
        position_panel.setVisible(visible)


def sync_strategy_workspace_from_preset(page: WatchlistHost, preset_id: LayoutPresetId) -> None:
    """工作区展开时，按预设同步信号/持仓区折叠态。"""
    spec = PRESET_SPECS[preset_id]
    signal_panel = getattr(page, "signal_panel", None)
    if signal_panel is not None:
        signal_panel.set_expanded(spec.signal_expanded, emit=True)
        save_signal_panel_expanded(spec.signal_expanded)
    position_panel = getattr(page, "position_panel", None)
    if position_panel is not None:
        position_panel.set_expanded(spec.position_expanded, emit=True)
        save_position_panel_expanded(spec.position_expanded)


def apply_strategy_workspace(
    page: WatchlistHost,
    open_state: bool,
    *,
    persist: bool = True,
    apply_preset: bool = False,
) -> None:
    page._strategy_workspace_open = open_state
    set_strategy_panels_visible(page, open_state)
    if open_state and apply_preset:
        sync_strategy_workspace_from_preset(page, load_watchlist_layout_preset())
    apply_toolbar_for_preset(page, load_watchlist_layout_preset())
    refresh_strategy_workspace_button(page)
    QtCore.QTimer.singleShot(0, lambda: apply_center_splitter_sizes(page))
    if persist:
        save_strategy_workspace_open(open_state)


def open_strategy_workspace(page: WatchlistHost, *, persist: bool = True) -> None:
    if is_strategy_workspace_open(page):
        return
    apply_strategy_workspace(page, True, persist=persist, apply_preset=True)


def refresh_strategy_workspace_button(page: WatchlistHost) -> None:
    button = getattr(page, "strategy_workspace_button", None)
    if button is None:
        return
    position_service = page._get_position_service()
    position_count = position_service.count() if position_service is not None else 0
    label = format_strategy_workspace_button_label(
        signal_count=_signal_count(page),
        position_count=position_count,
    )
    button.blockSignals(True)
    button.setText(label)
    button.setChecked(is_strategy_workspace_open(page))
    button.blockSignals(False)
    button.setToolTip("展开或收起策略信号区与持仓区。关闭时主表占满空间，后台仍刷新信号与持仓；展开后按当前预设（盘中/复盘）分配面板。")


def init_strategy_workspace_on_layout(page: WatchlistHost) -> None:
    """中部布局就绪后：应用工作区开闭并校正 splitter。"""
    open_state = load_strategy_workspace_open()
    apply_strategy_workspace(page, open_state, persist=False, apply_preset=open_state)
    from vnpy_ashare.ui.quotes.watchlist_signals.splitter import restore_center_splitter

    restore_center_splitter(page)


def _on_workspace_toggled(page: WatchlistHost, checked: bool) -> None:
    apply_strategy_workspace(page, checked, persist=True, apply_preset=checked)


def create_strategy_workspace_toolbar(page: WatchlistHost) -> QtWidgets.QPushButton:
    """策略/持仓主控：可切换按钮。"""
    parent = as_qwidget(page)
    toggle = QtWidgets.QPushButton("", parent)
    toggle.setObjectName("SecondaryButton")
    toggle.setCheckable(True)
    toggle.clicked.connect(lambda checked: _on_workspace_toggled(page, checked))
    page.strategy_workspace_button = toggle
    refresh_strategy_workspace_button(page)
    return toggle


def append_strategy_workspace_more_actions(
    page: WatchlistHost,
    more_actions: list[tuple[str, QtWidgets.QPushButton]],
) -> None:
    """策略工作区：池操作改由主表右键；情绪周期与笔记中心在工具栏/菜单栏展示。"""
    _ = more_actions
    page.add_signal_panel_button.hide()
