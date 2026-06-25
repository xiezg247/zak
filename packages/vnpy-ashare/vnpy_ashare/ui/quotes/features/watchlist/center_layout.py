"""自选页中部布局（分组 Tab、上下文条、主表/信号/持仓 splitter）。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.ui.components.task_run_output_panel import TaskRunOutputPanel
from vnpy_ashare.ui.quotes.features.watchlist.context_bar import WatchlistPoolContextBar
from vnpy_ashare.ui.quotes.features.watchlist.lazy_build import watchlist_lazy_build_enabled
from vnpy_ashare.ui.quotes.page.run_log import load_run_output_expanded, on_run_output_expansion_changed
from vnpy_ashare.ui.quotes.panels.loading_overlay import MarketTableHost
from vnpy_ashare.ui.quotes.watchlist.host import WatchlistHost
from vnpy_ashare.ui.quotes.watchlist_groups.tab_bar import WatchlistGroupTabBar
from vnpy_ashare.ui.quotes.watchlist_multiview.panel import WatchlistMultiViewBoard
from vnpy_ashare.ui.quotes.watchlist_positions.panel import WatchlistPositionPanel
from vnpy_ashare.ui.quotes.watchlist_signals.panel import WatchlistSignalPanel
from vnpy_ashare.ui.quotes.watchlist_signals.splitter import (
    bind_center_splitter_persistence,
    configure_center_splitter,
    restore_center_splitter,
)


def _wire_multiview_toolbar(page: WatchlistHost) -> None:
    if page.view_table_button is not None:
        page.view_table_button.clicked.connect(lambda: page._multiview.set_view_mode("table"))
    if page.view_multiview_button is not None:
        page.view_multiview_button.clicked.connect(lambda: page._multiview.set_view_mode("multiview"))


def build_watchlist_center_layout(page: WatchlistHost, center_layout: QtWidgets.QVBoxLayout) -> None:
    """组装自选页中部区域并挂载到 center_layout。"""
    lazy = watchlist_lazy_build_enabled(page)
    page.watchlist_group_tab_bar = None
    if page.config.show_watchlist_groups:
        parent = center_layout.parentWidget()
        page.watchlist_group_tab_bar = WatchlistGroupTabBar(parent)
        center_layout.addWidget(page.watchlist_group_tab_bar)

    page.watchlist_pool_context_bar = WatchlistPoolContextBar(page)
    center_layout.addWidget(page.watchlist_pool_context_bar)

    page._market_table_host = MarketTableHost(
        page.market_table,
        external_scrollbar=False,
    )
    center_primary: QtWidgets.QWidget = page._market_table_host
    page._center_view_stack = None
    page.multiview_board = None
    if page.config.show_watchlist_multiview:
        page._center_view_stack = QtWidgets.QStackedWidget()
        page._center_view_stack.setObjectName("WatchlistCenterViewStack")
        page._center_view_stack.addWidget(page._market_table_host)
        if not lazy:
            page.multiview_board = WatchlistMultiViewBoard(page)
            page._center_view_stack.addWidget(page.multiview_board)
        center_primary = page._center_view_stack

    use_center_split = page.config.show_watchlist_signals or page.config.show_watchlist_positions or page.config.show_run_output_panel
    if use_center_split:
        center_split = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        configure_center_splitter(center_split)
        center_split.addWidget(center_primary)
        if lazy:
            page.signal_panel = None
            page.position_panel = None
        else:
            if page.config.show_watchlist_signals:
                page.signal_panel = WatchlistSignalPanel(page)
                center_split.addWidget(page.signal_panel)
            if page.config.show_watchlist_positions:
                page.position_panel = WatchlistPositionPanel(page)
                center_split.addWidget(page.position_panel)
        if page.config.show_run_output_panel:
            run_prefix = "Watchlist" if page.page_name == "自选" else "Local"
            page.run_output_panel = TaskRunOutputPanel(
                title="运行输出",
                log_placeholder="暂无执行日志",
                object_name=f"{run_prefix}RunOutputPanel",
                section_label_object_name=f"{run_prefix}SectionLabel",
                summary_object_name=f"{run_prefix}RunSummary",
                log_view_object_name=f"{run_prefix}RunLogView",
                expanded=load_run_output_expanded(page.page_name),
            )
            page.run_output_panel.expansion_changed.connect(
                lambda expanded: on_run_output_expansion_changed(page, expanded),
            )
            center_split.addWidget(page.run_output_panel)
        page._center_splitter = center_split
        center_layout.addWidget(center_split, stretch=1)
        if not lazy:
            bind_center_splitter_persistence(page)
            QtCore.QTimer.singleShot(0, lambda: restore_center_splitter(page))
    else:
        center_layout.addWidget(center_primary, stretch=1)

    if page.config.show_watchlist_multiview:
        if lazy:
            _wire_multiview_toolbar(page)
        else:
            page._wire_multiview()
    if not lazy:
        if page.config.show_watchlist_signals:
            page._wire_signal_panel()
        if page.config.show_watchlist_positions:
            page._wire_position_panel()
