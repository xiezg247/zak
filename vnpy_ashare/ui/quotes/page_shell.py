"""QuotesPage 布局与控件初始化。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.minute_periods import LOCAL_SCOPE_OPTIONS
from vnpy_ashare.ui.chart_panel import ChartPanel
from vnpy_ashare.ui.chart_style import CHART_FRAME_STYLESHEET
from vnpy_ashare.ui.depth_panel import DepthPanel
from vnpy_ashare.ui.diagnose_panel import DiagnosePanel
from vnpy_ashare.ui.ma_legend import MaLegendBar
from vnpy_ashare.ui.quote_columns import LOCAL_TABLE_HEADERS
from vnpy_ashare.ui.quotes_chart import create_daily_chart
from vnpy_ashare.ui.quotes_config import quote_refresh_hint
from vnpy_ashare.ui.styles import NAV_MUTED_COLOR, apply_toolbar_combo_style

if TYPE_CHECKING:
    from vnpy_ashare.ui.quotes_page import QuotesPage


class QuotesPageShell:
    """构建 QuotesPage 工具栏、表格与右侧详情区。"""

    def __init__(self, page: QuotesPage) -> None:
        self._page = page

    def build(self) -> None:
        page = self._page
        page._init_columns()
        if page.config.use_local_table:
            headers = LOCAL_TABLE_HEADERS
        else:
            headers = page._build_visible_headers()

        page.search_edit = QtWidgets.QLineEdit()
        page.search_edit.setObjectName("SearchBox")
        page.search_edit.setPlaceholderText(page.config.search_placeholder)
        page.search_edit.textChanged.connect(lambda _: page._search_timer.start())

        page.board_combo = QtWidgets.QComboBox()
        page.board_combo.setObjectName("BoardCombo")
        page.board_combo.addItems(["全部", "沪深主板", "创业板", "科创板", "北交所"])
        page.board_combo.setVisible(page.config.show_board_filter)
        page.board_combo.currentIndexChanged.connect(page._on_board_changed)

        page.sync_button = QtWidgets.QPushButton("同步 A 股列表")
        page.sync_button.clicked.connect(page.sync_universe_clicked)
        page.sync_button.setVisible(page.config.show_sync_button)

        page.download_button = QtWidgets.QPushButton("下载日K到本地")
        page.download_button.clicked.connect(page.download_selected)
        page.download_button.setEnabled(False)
        page.download_button.setVisible(page.config.show_download_button)

        page.fill_button = QtWidgets.QPushButton("补全到最新")
        page.fill_button.clicked.connect(page.fill_selected)
        page.fill_button.setEnabled(False)
        page.fill_button.setVisible(page.config.show_fill_button)

        page.redownload_button = QtWidgets.QPushButton("重新下载")
        page.redownload_button.clicked.connect(page.redownload_selected)
        page.redownload_button.setEnabled(False)
        page.redownload_button.setVisible(page.config.show_redownload_button)

        page.local_period_combo = QtWidgets.QComboBox()
        for label, value in LOCAL_SCOPE_OPTIONS:
            page.local_period_combo.addItem(label, value)
        apply_toolbar_combo_style(page.local_period_combo)
        page.local_period_combo.setVisible(page.config.use_local_table)
        page.local_period_combo.currentIndexChanged.connect(page._on_local_period_changed)

        page.add_watchlist_button = QtWidgets.QPushButton("加入自选")
        page.add_watchlist_button.clicked.connect(page._watchlist.add_selected)
        page.add_watchlist_button.setEnabled(False)
        page.add_watchlist_button.setVisible(page.config.show_add_watchlist_button)

        page.remove_watchlist_button = QtWidgets.QPushButton("移出自选")
        page.remove_watchlist_button.clicked.connect(page._watchlist.remove_selected)
        page.remove_watchlist_button.setEnabled(False)
        page.remove_watchlist_button.setVisible(page.config.show_remove_watchlist_button)

        page.move_watchlist_up_button = QtWidgets.QPushButton("上移")
        page.move_watchlist_up_button.clicked.connect(
            lambda: page._watchlist.move_selected("up")
        )
        page.move_watchlist_up_button.setEnabled(False)
        page.move_watchlist_up_button.setVisible(page.config.show_watchlist_move_buttons)

        page.move_watchlist_down_button = QtWidgets.QPushButton("下移")
        page.move_watchlist_down_button.clicked.connect(
            lambda: page._watchlist.move_selected("down")
        )
        page.move_watchlist_down_button.setEnabled(False)
        page.move_watchlist_down_button.setVisible(page.config.show_watchlist_move_buttons)

        page.backtest_button = QtWidgets.QPushButton("策略回测")
        page.backtest_button.clicked.connect(page._actions.open_backtest_for_selected)
        page.backtest_button.setEnabled(False)
        page.backtest_button.setVisible(page.config.show_backtest_button)

        page.diagnose_button = QtWidgets.QPushButton("诊断")
        page.diagnose_button.clicked.connect(page._actions.run_diagnose_for_selected)
        page.diagnose_button.setEnabled(False)
        page.diagnose_button.setVisible(page.config.show_diagnose_button)

        page.refresh_quotes_button = QtWidgets.QPushButton("刷新行情")
        page.refresh_quotes_button.clicked.connect(page._refresh_market_clicked)
        page.refresh_quotes_button.setVisible(page.config.use_market_rank)

        toolbar = QtWidgets.QHBoxLayout()
        toolbar.addWidget(page.search_edit, stretch=1)
        if page.config.show_board_filter:
            toolbar.addWidget(page.board_combo)

        # ── 分隔线 ──
        group2_visible = page.config.use_market_rank or page.config.show_sync_button
        if group2_visible:
            sep1 = QtWidgets.QFrame()
            sep1.setObjectName("ToolbarSeparator")
            sep1.setFrameShape(QtWidgets.QFrame.Shape.VLine)
            toolbar.addWidget(sep1)

        if page.config.use_market_rank:
            toolbar.addWidget(page.refresh_quotes_button)
        if page.config.show_sync_button:
            toolbar.addWidget(page.sync_button)

        # ── 分隔线 ──
        group3_visible = (
            page.config.show_add_watchlist_button
            or page.config.show_download_button
            or page.config.show_backtest_button
        )
        if group2_visible and group3_visible:
            sep2 = QtWidgets.QFrame()
            sep2.setObjectName("ToolbarSeparator")
            sep2.setFrameShape(QtWidgets.QFrame.Shape.VLine)
            toolbar.addWidget(sep2)

        if page.config.use_local_table:
            toolbar.addWidget(page.local_period_combo)
        if page.config.show_add_watchlist_button:
            toolbar.addWidget(page.add_watchlist_button)
        if page.config.show_remove_watchlist_button:
            toolbar.addWidget(page.remove_watchlist_button)
        if page.config.show_watchlist_move_buttons:
            toolbar.addWidget(page.move_watchlist_up_button)
            toolbar.addWidget(page.move_watchlist_down_button)
        if page.config.show_download_button:
            toolbar.addWidget(page.download_button)
        if page.config.show_fill_button:
            toolbar.addWidget(page.fill_button)
        if page.config.show_redownload_button:
            toolbar.addWidget(page.redownload_button)
        if page.config.show_backtest_button:
            toolbar.addWidget(page.backtest_button)
        if page.config.show_diagnose_button:
            toolbar.addWidget(page.diagnose_button)
        if page.config.column_configurable:
            page.column_button = QtWidgets.QPushButton("列 ▾")
            page.column_button.setObjectName("ColumnButton")
            page.column_button.clicked.connect(page._table.show_column_menu)
            toolbar.addWidget(page.column_button)

        page.prev_page_button = QtWidgets.QPushButton("◀ 上一页")
        page.prev_page_button.clicked.connect(page._go_prev_page)
        page.next_page_button = QtWidgets.QPushButton("下一页 ▶")
        page.next_page_button.clicked.connect(page._go_next_page)
        page.page_label = QtWidgets.QLabel("")
        page.page_total_label = QtWidgets.QLabel("")

        page.home_button = QtWidgets.QPushButton("⏮ 首页")
        page.home_button.clicked.connect(page._go_home_page)
        page.end_button = QtWidgets.QPushButton("尾页 ⏭")
        page.end_button.clicked.connect(page._go_end_page)
        page.page_jump_input = QtWidgets.QLineEdit()
        page.page_jump_input.setObjectName("PageJumpInput")
        page.page_jump_input.setPlaceholderText("跳页")
        page.page_jump_input.setFixedWidth(52)
        page.page_jump_input.returnPressed.connect(page._page_jump)

        page.pagination_bar = QtWidgets.QHBoxLayout()
        page.pagination_bar.addWidget(page.home_button)
        page.pagination_bar.addWidget(page.prev_page_button)
        page.pagination_bar.addWidget(page.page_label)
        page.pagination_bar.addWidget(page.page_jump_input)
        page.pagination_bar.addWidget(page.page_total_label)
        page.pagination_bar.addWidget(page.next_page_button)
        page.pagination_bar.addWidget(page.end_button)
        page._set_pagination_visible(page.config.use_market_rank)

        page.stats_label = QtWidgets.QLabel("")
        page.stats_label.setObjectName("StatsLabel")
        page.stats_label.setStyleSheet(f"color: {NAV_MUTED_COLOR}; padding: 2px 6px;")
        page.stats_label.setVisible(page.config.column_configurable)

        page.market_table = QtWidgets.QTableWidget()
        page.market_table.setObjectName("MarketTable")
        page.market_table.setColumnCount(len(headers))
        page.market_table.setHorizontalHeaderLabels(headers)
        page.market_table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows
        )
        page.market_table.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.SingleSelection
        )
        page.market_table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers
        )
        page.market_table.verticalHeader().setVisible(False)
        page.market_table.setAlternatingRowColors(True)
        page.market_table.setSortingEnabled(False)
        page.market_table.itemSelectionChanged.connect(page._table.on_selection_changed)
        page.market_table.setContextMenuPolicy(
            QtCore.Qt.ContextMenuPolicy.CustomContextMenu
        )
        page.market_table.customContextMenuRequested.connect(page._actions.show_context_menu)
        if page.config.table_header_sortable:
            page.market_table.horizontalHeader().setSortIndicatorShown(True)
            page.market_table.horizontalHeader().setSectionsClickable(True)

        page._table.apply_header_layout(column_count=len(headers))

        page.quote_name_label = QtWidgets.QLabel("—")
        page.quote_name_label.setObjectName("QuoteHeader")
        page.quote_code_label = QtWidgets.QLabel("")
        page.quote_price_label = QtWidgets.QLabel("—")
        page.quote_price_label.setObjectName("QuoteHeader")
        page.quote_change_label = QtWidgets.QLabel("")
        if page.config.hide_quote_header:
            page.quote_name_label.hide()
            page.quote_code_label.hide()
            page.quote_price_label.hide()
            page.quote_change_label.hide()
        elif page.config.use_local_table:
            page.quote_price_label.hide()
            page.quote_change_label.hide()

        quote_info = QtWidgets.QHBoxLayout()
        quote_info.addWidget(page.quote_name_label)
        quote_info.addWidget(page.quote_code_label)
        quote_info.addStretch()
        quote_info.addWidget(page.quote_price_label)
        quote_info.addWidget(page.quote_change_label)

        page.quote_sub_info = QtWidgets.QHBoxLayout()
        page._open_label = QtWidgets.QLabel("")
        page._high_label = QtWidgets.QLabel("")
        page._low_label = QtWidgets.QLabel("")
        page._volume_label = QtWidgets.QLabel("")
        for lbl in (page._open_label, page._high_label, page._low_label, page._volume_label):
            lbl.setObjectName("QuoteSubInfo")
            lbl.setStyleSheet(f"color: {NAV_MUTED_COLOR}; font-size: 12px;")
        page.quote_sub_info.addStretch()
        page.quote_sub_info.addWidget(page._open_label)
        page.quote_sub_info.addWidget(page._high_label)
        page.quote_sub_info.addWidget(page._low_label)
        page.quote_sub_info.addWidget(page._volume_label)

        if page.config.show_chart_tabs:
            page.chart_panel = ChartPanel()
            page.chart_panel.tab_changed.connect(page._on_chart_tab_changed)
            page._on_chart_tab_changed(page.chart_panel.current_tab_index())
            chart_widget = page.chart_panel
        elif not page.config.show_kline:
            chart_widget = None
        else:
            page.chart = create_daily_chart()
            chart_frame = QtWidgets.QWidget()
            chart_frame.setObjectName("ChartFrame")
            chart_frame.setStyleSheet(CHART_FRAME_STYLESHEET)
            frame_layout = QtWidgets.QVBoxLayout(chart_frame)
            frame_layout.setContentsMargins(4, 4, 4, 4)
            frame_layout.setSpacing(0)

            page.chart_hint = QtWidgets.QLabel("选中标的后显示日K")
            page.chart_hint.setObjectName("ChartHint")
            page.chart_hint.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

            frame_layout.addWidget(MaLegendBar())
            frame_layout.addWidget(page.chart, stretch=1)
            frame_layout.addWidget(page.chart_hint)
            chart_widget = chart_frame

        if page.config.show_kline:
            chart_row = QtWidgets.QHBoxLayout()
            chart_row.setSpacing(6)
            if chart_widget is not None:
                chart_row.addWidget(chart_widget, stretch=1)
            if page.config.show_depth_panel:
                page.depth_panel = DepthPanel()
                chart_row.addWidget(page.depth_panel)

            right_panel = QtWidgets.QVBoxLayout()
            right_panel.addLayout(quote_info)
            if page.config.column_configurable:
                right_panel.addLayout(page.quote_sub_info)
            if page.config.show_diagnose_panel:
                page.diagnose_panel = DiagnosePanel()
                page.diagnose_panel.refresh_requested.connect(page.run_diagnose_for_selected)
                right_panel.addWidget(page.diagnose_panel)
            right_panel.addLayout(chart_row, stretch=1)

            splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
            page._splitter = splitter
            center_widget = QtWidgets.QWidget()
            center_layout = QtWidgets.QVBoxLayout(center_widget)
            center_layout.setContentsMargins(0, 0, 0, 0)
            center_layout.addLayout(toolbar)
            if page.stats_label is not None:
                center_layout.addWidget(page.stats_label)
            center_layout.addWidget(page.market_table)
            center_layout.addLayout(page.pagination_bar)
            splitter.addWidget(center_widget)

            right_widget = QtWidgets.QWidget()
            right_widget.setLayout(right_panel)
            right_widget.setMinimumWidth(560 if page.config.show_depth_panel else 420)
            splitter.addWidget(right_widget)
            splitter.setStretchFactor(0, 3)
            splitter.setStretchFactor(1, 2)
        else:
            # 市场页：单栏全宽布局
            splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
            center_widget = QtWidgets.QWidget()
            center_layout = QtWidgets.QVBoxLayout(center_widget)
            center_layout.setContentsMargins(0, 0, 0, 0)
            center_layout.addLayout(toolbar)
            if page.stats_label is not None:
                center_layout.addWidget(page.stats_label)
            center_layout.addWidget(page.market_table)
            splitter.addWidget(center_widget)

        page.status_label = QtWidgets.QLabel("就绪")
        page.refresh_hint_label = QtWidgets.QLabel(
            quote_refresh_hint(
                auto_refresh=page.config.auto_refresh_quotes,
                refresh_ms=page.config.quote_refresh_ms,
                quote_source=page.config.quote_source,
            )
        )
        page.refresh_hint_label.setStyleSheet(f"color: {NAV_MUTED_COLOR};")

        bottom_bar = QtWidgets.QHBoxLayout()
        bottom_bar.setContentsMargins(8, 2, 8, 4)
        bottom_bar.addWidget(page.status_label, stretch=1)
        bottom_bar.addStretch()
        bottom_bar.addWidget(page.home_button)
        bottom_bar.addWidget(page.prev_page_button)
        bottom_bar.addWidget(page.page_label)
        bottom_bar.addWidget(page.page_jump_input)
        bottom_bar.addWidget(page.page_total_label)
        bottom_bar.addWidget(page.next_page_button)
        bottom_bar.addWidget(page.end_button)
        bottom_bar.addStretch()
        bottom_bar.addWidget(page.refresh_hint_label)

        root = QtWidgets.QVBoxLayout(page)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(splitter, stretch=1)
        root.addLayout(bottom_bar)
