"""自选页重型 UI 延迟构建（ChartPanel / 信号区 / 持仓区 / 多维看盘）。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.ui.components.chart_style import build_chart_frame_stylesheet
from vnpy_ashare.ui.quotes._host_widget import as_qwidget
from vnpy_ashare.ui.quotes.chart.panel import ChartPanel
from vnpy_ashare.ui.quotes.features.watchlist.strategy_workspace import (
    init_strategy_workspace_on_layout,
    strategy_workspace_pref_open,
)
from vnpy_ashare.ui.quotes.panels.depth import DepthPanel
from vnpy_ashare.ui.quotes.stock_notes.panel import StockNotePanel
from vnpy_ashare.ui.quotes.watchlist_multiview.panel import WatchlistMultiViewBoard
from vnpy_ashare.ui.quotes.watchlist_positions.panel import WatchlistPositionPanel
from vnpy_ashare.ui.quotes.watchlist_signals.panel import WatchlistSignalPanel
from vnpy_ashare.ui.quotes.watchlist_signals.splitter import bind_center_splitter_persistence
from vnpy_common.ui.theme.manager import theme_manager

if TYPE_CHECKING:
    from vnpy_ashare.ui.quotes.watchlist.host import WatchlistHost


class WatchlistLazyBuildCoordinator:
    """首屏仅建主表与壳层；重型面板在首次激活或切换视图时再挂载。"""

    def __init__(self) -> None:
        self._chart_ready = False
        self._strategy_panels_ready = False
        self._multiview_ready = False

    @property
    def chart_ready(self) -> bool:
        return self._chart_ready

    @property
    def strategy_panels_ready(self) -> bool:
        return self._strategy_panels_ready

    def ensure_for_activate(self, page: WatchlistHost, *, include_multiview: bool = False) -> None:
        if strategy_workspace_pref_open():
            self.ensure_strategy_panels(page)
        self.ensure_chart_side(page)
        if include_multiview:
            self.ensure_multiview(page)

    def ensure_strategy_panels(self, page: WatchlistHost) -> None:
        if self._strategy_panels_ready:
            return
        splitter = getattr(page, "_center_splitter", None)
        if splitter is None:
            self._strategy_panels_ready = True
            return

        if page.config.show_watchlist_signals and getattr(page, "signal_panel", None) is None:
            page.signal_panel = WatchlistSignalPanel(page)
            splitter.addWidget(page.signal_panel)
            page._wire_signal_panel()

        if page.config.show_watchlist_positions and getattr(page, "position_panel", None) is None:
            page.position_panel = WatchlistPositionPanel(page)
            splitter.addWidget(page.position_panel)
            page._wire_position_panel()

        if splitter.parentWidget() is not None and not getattr(page, "_center_splitter_bound", False):
            bind_center_splitter_persistence(page)

        init_strategy_workspace_on_layout(page)
        self._strategy_panels_ready = True

    def ensure_chart_side(self, page: WatchlistHost) -> None:
        if self._chart_ready:
            return
        if not page.config.show_chart_tabs:
            self._chart_ready = True
            return

        chart_row: QtWidgets.QHBoxLayout | None = getattr(page, "_lazy_chart_row", None)
        if chart_row is None:
            self._chart_ready = True
            return

        page.chart_panel = ChartPanel()
        page.chart_panel.tab_changed.connect(page._on_chart_tab_changed)
        page._on_chart_tab_changed(page.chart_panel.current_tab_index())
        chart_row.addWidget(page.chart_panel, stretch=1)

        if page.config.show_depth_panel:
            page.depth_panel = DepthPanel()
            chart_row.addWidget(page.depth_panel)

        right_panel: QtWidgets.QVBoxLayout | None = getattr(page, "_lazy_right_panel", None)
        if page.config.show_stock_notes and right_panel is not None and getattr(page, "stock_note_panel", None) is None:
            page.stock_note_panel = StockNotePanel(page)
            right_panel.addWidget(page.stock_note_panel)
            page._wire_stock_note_panel()

        self._chart_ready = True

    def ensure_multiview(self, page: WatchlistHost) -> None:
        if self._multiview_ready or not page.config.show_watchlist_multiview:
            return
        stack = getattr(page, "_center_view_stack", None)
        if stack is None or getattr(page, "multiview_board", None) is not None:
            self._multiview_ready = True
            return

        board = WatchlistMultiViewBoard(as_qwidget(page))
        page.multiview_board = board
        stack.addWidget(board)
        page._multiview.wire_board(board)
        self._multiview_ready = True


def watchlist_lazy_build_enabled(page: WatchlistHost) -> bool:
    return getattr(page, "_watchlist_lazy", None) is not None


def create_lazy_chart_row_host(page: WatchlistHost) -> QtWidgets.QWidget:
    """占位图表行：首次激活时再填入 ChartPanel / DepthPanel。"""
    page._lazy_chart_row = QtWidgets.QHBoxLayout()
    page._lazy_chart_row.setSpacing(6)

    host = QtWidgets.QWidget()
    host.setLayout(page._lazy_chart_row)
    host.setObjectName("LazyChartRowHost")
    theme_manager().bind_stylesheet(host, extra=build_chart_frame_stylesheet)
    return host
