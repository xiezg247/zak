"""策略监控页 feature：池上下文与布局聚焦（无盘中/复盘工具栏）。"""

from __future__ import annotations

from vnpy.trader.ui import QtWidgets

from vnpy_ashare.ui.quotes.features.strategy_monitor.center_layout import build_strategy_monitor_center_layout
from vnpy_ashare.ui.quotes.features.watchlist.context_bar import WatchlistPoolContextBar
from vnpy_ashare.ui.quotes.features.watchlist.layout_preset import apply_layout_preset, apply_position_focus
from vnpy_ashare.ui.quotes.features.watchlist.prefs import LayoutPresetId
from vnpy_ashare.ui.quotes.watchlist.host import WatchlistHost


class StrategyMonitorPageFeature:
    def __init__(self, page: WatchlistHost) -> None:
        self._page = page
        self.pool_context_bar: WatchlistPoolContextBar | None = None

    def prepend_toolbar_widgets(self, toolbar: QtWidgets.QHBoxLayout) -> None:
        _ = toolbar

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
        self.refresh_context_bar()

    def on_stock_list_loaded(self) -> None:
        self.refresh_context_bar()

    def refresh_context_bar(self) -> None:
        bar = self.pool_context_bar or getattr(self._page, "watchlist_pool_context_bar", None)
        if isinstance(bar, WatchlistPoolContextBar):
            bar.refresh()

    def apply_layout_preset(self, preset_id: LayoutPresetId) -> None:
        """自选页 context bar 跳转时聚焦信号区（盘中布局）。"""
        apply_layout_preset(self._page, preset_id)

    def apply_position_focus(self) -> None:
        """自选页 context bar 跳转时聚焦持仓区。"""
        apply_position_focus(self._page)
