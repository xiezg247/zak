"""自选页工具栏控件（工作流预设、表格/多维切换、自选分支动作收拢）。"""

from __future__ import annotations

from vnpy.trader.ui import QtWidgets

from vnpy_ashare.ui.quotes._host_widget import as_qwidget
from vnpy_ashare.ui.quotes.features.watchlist.layout_preset import layout_preset_options
from vnpy_ashare.ui.quotes.features.watchlist.prefs import load_watchlist_layout_preset
from vnpy_ashare.ui.quotes.features.watchlist.strategy_workspace import (
    append_strategy_workspace_more_actions,
    create_strategy_workspace_toolbar,
)
from vnpy_ashare.ui.quotes.features.watchlist.toolbar_policy import (
    WatchlistToolbarPolicy,
    configure_watchlist_action_button_visibility,
    watchlist_toolbar_group3_visible,
    watchlist_toolbar_policy,
)
from vnpy_ashare.ui.quotes.market_overview.emotion_cycle_chip import EmotionCycleChip
from vnpy_ashare.ui.quotes.watchlist.host import WatchlistHost
from vnpy_ashare.ui.quotes.watchlist.pool_host import WatchlistPoolHost
from vnpy_ashare.ui.styles.vnpy_page import apply_toolbar_combo_style

__all__ = [
    "WatchlistToolbarPolicy",
    "append_watchlist_pool_toolbar_actions",
    "append_watchlist_strategy_toolbar_actions",
    "configure_watchlist_action_button_visibility",
    "create_layout_preset_combo",
    "create_strategy_workspace_toolbar",
    "create_view_mode_buttons",
    "watchlist_toolbar_group3_visible",
    "watchlist_toolbar_policy",
]


def append_watchlist_pool_toolbar_actions(
    page: WatchlistPoolHost,
    toolbar: QtWidgets.QHBoxLayout,
    more_actions: list[tuple[str, QtWidgets.QPushButton]],
    *,
    policy: WatchlistToolbarPolicy | None,
    show_move_in_toolbar: bool,
) -> None:
    """自选池相关：加入/移出/排序/下载。"""
    if page.config.show_add_watchlist_button:
        toolbar.addWidget(page.add_watchlist_button)
    if page.config.show_remove_watchlist_button:
        if policy is not None:
            page.remove_watchlist_button.hide()
        else:
            toolbar.addWidget(page.remove_watchlist_button)
    if show_move_in_toolbar:
        more_actions.extend(
            [
                ("上移", page.move_watchlist_up_button),
                ("下移", page.move_watchlist_down_button),
            ]
        )
    if page.config.show_download_button and policy is None:
        toolbar.addWidget(page.download_button)


def append_watchlist_strategy_toolbar_actions(
    page: WatchlistHost,
    toolbar: QtWidgets.QHBoxLayout,
    more_actions: list[tuple[str, QtWidgets.QPushButton]],
    *,
    policy: WatchlistToolbarPolicy | None,
    show_backtest_in_toolbar: bool,
    show_diagnose_in_toolbar: bool,
) -> None:
    """信号/持仓/笔记/诊断等自选页策略区动作。"""
    if show_backtest_in_toolbar:
        toolbar.addWidget(page.backtest_button)
    if page.config.show_batch_backtest_button:
        more_actions.append(("批量回测", page.batch_backtest_button))
    has_strategy_workspace = policy is not None and (page.config.show_watchlist_signals or page.config.show_watchlist_positions)
    if has_strategy_workspace:
        toolbar.addWidget(create_strategy_workspace_toolbar(page))
        if page.config.show_watchlist_signals or page.config.show_watchlist_positions:
            parent = as_qwidget(page)
            page.emotion_cycle_chip = EmotionCycleChip(parent)
            toolbar.addWidget(page.emotion_cycle_chip)
        append_strategy_workspace_more_actions(page, more_actions)
    else:
        if page.config.show_watchlist_signals:
            toolbar.addWidget(page.add_signal_panel_button)
        if page.config.show_watchlist_signals or page.config.show_watchlist_positions:
            parent = as_qwidget(page)
            page.emotion_cycle_chip = EmotionCycleChip(parent)
            toolbar.addWidget(page.emotion_cycle_chip)
    if page.config.show_stock_notes:
        toolbar.addWidget(page.quick_note_button)
        if policy is None:
            toolbar.addWidget(page.notes_center_button)
        else:
            page.notes_center_button.hide()
    if show_diagnose_in_toolbar:
        toolbar.addWidget(page.diagnose_button)
    if page.config.show_refresh_quotes_button and not page.config.use_market_rank:
        if policy is not None:
            page.refresh_quotes_button.hide()
        else:
            toolbar.addWidget(page.refresh_quotes_button)


def create_layout_preset_combo(page: WatchlistHost) -> QtWidgets.QComboBox:
    combo = QtWidgets.QComboBox(as_qwidget(page))
    combo.setObjectName("WatchlistLayoutPresetCombo")
    apply_toolbar_combo_style(combo)
    for preset_id, label in layout_preset_options():
        combo.addItem(label, preset_id)
    active = load_watchlist_layout_preset()
    index = combo.findData(active)
    if index >= 0:
        combo.setCurrentIndex(index)
    feature = page._watchlist_feature
    if feature is not None:
        combo.currentIndexChanged.connect(lambda _index: feature.on_layout_preset_changed())
    return combo


def create_view_mode_buttons(page: WatchlistHost) -> tuple[QtWidgets.QPushButton, QtWidgets.QPushButton]:
    parent = as_qwidget(page)
    table_button = QtWidgets.QPushButton("表格", parent)
    table_button.setObjectName("SecondaryButton")
    table_button.setCheckable(True)
    table_button.setChecked(True)

    multiview_button = QtWidgets.QPushButton("多维", parent)
    multiview_button.setObjectName("SecondaryButton")
    multiview_button.setCheckable(True)
    return table_button, multiview_button
