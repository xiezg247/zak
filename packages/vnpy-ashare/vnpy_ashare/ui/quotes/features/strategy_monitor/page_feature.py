"""策略监控页 feature：工具栏预设与池上下文。"""

from __future__ import annotations

from vnpy.trader.ui import QtWidgets

from vnpy_ashare.ui.quotes.features.strategy_monitor.center_layout import build_strategy_monitor_center_layout
from vnpy_ashare.ui.quotes.features.watchlist.context_bar import WatchlistPoolContextBar
from vnpy_ashare.ui.quotes.features.watchlist.layout_preset import apply_layout_preset, apply_position_focus
from vnpy_ashare.ui.quotes.features.watchlist.prefs import LayoutPresetId, load_watchlist_layout_preset
from vnpy_ashare.ui.quotes.features.watchlist.toolbar import create_layout_preset_combo
from vnpy_ashare.ui.quotes.watchlist.host import WatchlistHost


class StrategyMonitorPageFeature:
    def __init__(self, page: WatchlistHost) -> None:
        self._page = page
        self.layout_preset_combo: QtWidgets.QComboBox | None = None
        self.pool_context_bar: WatchlistPoolContextBar | None = None

    def prepend_toolbar_widgets(self, toolbar: QtWidgets.QHBoxLayout) -> None:
        self.layout_preset_combo = create_layout_preset_combo(self._page)
        toolbar.addWidget(self.layout_preset_combo)

    def build_center_layout(self, center_layout: QtWidgets.QVBoxLayout) -> None:
        build_strategy_monitor_center_layout(self._page, center_layout)
        bar = getattr(self._page, "watchlist_pool_context_bar", None)
        if isinstance(bar, WatchlistPoolContextBar):
            self.pool_context_bar = bar

    def wire(self) -> None:
        page = self._page
        signal_panel = getattr(page, "signal_panel", None)
        if signal_panel is not None:
            signal_panel.symbols_changed.connect(self.refresh_context_bar)
        position_panel = getattr(page, "position_panel", None)
        if position_panel is not None:
            position_panel.rows_changed.connect(self.refresh_context_bar)

    def on_activate(self) -> None:
        preset = load_watchlist_layout_preset()
        apply_layout_preset(self._page, preset, persist=False, apply_splitter=True)
        self.refresh_context_bar()

    def on_stock_list_loaded(self) -> None:
        self.refresh_context_bar()

    def refresh_context_bar(self) -> None:
        bar = self.pool_context_bar or getattr(self._page, "watchlist_pool_context_bar", None)
        if isinstance(bar, WatchlistPoolContextBar):
            bar.refresh()

    def on_layout_preset_changed(self) -> None:
        combo = self.layout_preset_combo
        if combo is None:
            return
        preset_id = combo.currentData()
        if not isinstance(preset_id, str):
            return
        apply_layout_preset(self._page, preset_id)  # type: ignore[arg-type]

    def apply_layout_preset(self, preset_id: LayoutPresetId) -> None:
        combo = self.layout_preset_combo
        if combo is not None:
            index = combo.findData(preset_id)
            if index >= 0:
                combo.blockSignals(True)
                combo.setCurrentIndex(index)
                combo.blockSignals(False)
        apply_layout_preset(self._page, preset_id)

    def apply_position_focus(self) -> None:
        apply_position_focus(self._page)
