"""自选页工具栏控件（工作流预设、表格/多维切换）。"""

from __future__ import annotations

from vnpy.trader.ui import QtWidgets

from vnpy_ashare.ui.quotes.features.watchlist.layout_preset import layout_preset_options
from vnpy_ashare.ui.quotes.features.watchlist.prefs import load_watchlist_layout_preset
from vnpy_ashare.ui.styles.vnpy_page import apply_toolbar_combo_style

from vnpy_ashare.ui.quotes.watchlist.host import WatchlistHost


def create_layout_preset_combo(page: WatchlistHost) -> QtWidgets.QComboBox:
    combo = QtWidgets.QComboBox(page)
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
    table_button = QtWidgets.QPushButton("表格", page)
    table_button.setObjectName("SecondaryButton")
    table_button.setCheckable(True)
    table_button.setChecked(True)

    multiview_button = QtWidgets.QPushButton("多维", page)
    multiview_button.setObjectName("SecondaryButton")
    multiview_button.setCheckable(True)
    return table_button, multiview_button
