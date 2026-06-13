"""QuotesPage 布局与控件初始化。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vnpy.trader.ui import QtCore, QtGui, QtWidgets

from vnpy_ashare.data.minute_periods import LOCAL_SCOPE_OPTIONS
from vnpy_ashare.quotes.provider import is_gateway_quote_active
from vnpy_ashare.ui.components.chart_style import build_chart_frame_stylesheet
from vnpy_ashare.ui.components.task_run_output_panel import TaskRunOutputPanel
from vnpy_ashare.ui.quotes.chart import ChartPanel, ChartSectionPanel, create_daily_chart
from vnpy_ashare.ui.quotes.chart.ma_legend import MaLegendBar
from vnpy_ashare.ui.quotes.page.config import (
    load_market_auto_refresh_pref,
    quote_source_label,
)
from vnpy_ashare.ui.quotes.page.run_log import (
    load_run_output_expanded,
    on_run_output_expansion_changed,
)
from vnpy_ashare.ui.quotes.panels import DepthPanel, DiagnosePanel, MarketTableHost
from vnpy_ashare.ui.quotes.table import LOCAL_TABLE_HEADERS, QuoteTableModel
from vnpy_ashare.ui.quotes.watchlist_positions import WatchlistPositionPanel
from vnpy_ashare.ui.quotes.watchlist_signals import (
    WatchlistSignalPanel,
    bind_center_splitter_persistence,
    configure_center_splitter,
    restore_center_splitter,
)
from vnpy_ashare.ui.styles import apply_toolbar_combo_style
from vnpy_common.ui.feedback import PageToastHost
from vnpy_common.ui.theme import theme_manager

if TYPE_CHECKING:
    from vnpy_ashare.ui.quotes.page.quotes_page import QuotesPage


def _toolbar_separator() -> QtWidgets.QFrame:
    sep = QtWidgets.QFrame()
    sep.setObjectName("ToolbarSeparator")
    sep.setFrameShape(QtWidgets.QFrame.Shape.VLine)
    return sep


def _invoke_toolbar_action(button: QtWidgets.QPushButton) -> None:
    if button.isEnabled():
        button.click()


def _add_more_menu(
    toolbar: QtWidgets.QHBoxLayout,
    actions: list[tuple[str, QtWidgets.QPushButton]],
) -> None:
    if not actions:
        return
    menu_btn = QtWidgets.QPushButton("更多 ▾")
    menu_btn.setObjectName("SecondaryButton")
    menu = QtWidgets.QMenu(menu_btn)
    action_pairs: list[tuple[QtGui.QAction, QtWidgets.QPushButton]] = []
    for label, action_btn in actions:
        action = menu.addAction(label)
        action.triggered.connect(
            lambda _checked=False, btn=action_btn: _invoke_toolbar_action(btn),
        )
        action_pairs.append((action, action_btn))

    def _sync_menu_actions() -> None:
        for action, btn in action_pairs:
            action.setEnabled(btn.isEnabled())

    menu.aboutToShow.connect(_sync_menu_actions)
    menu_btn.setMenu(menu)
    toolbar.addWidget(menu_btn)


class QuotesPageShell:
    """构建 QuotesPage 工具栏、表格与右侧详情区。"""

    def __init__(self, page: QuotesPage) -> None:
        self._page = page

    def build(self) -> None:
        page = self._page
        if page.config.use_radar_cards:
            self._build_radar_layout(page)
            return
        page._init_columns()
        if page.config.use_local_table:
            headers = LOCAL_TABLE_HEADERS
        else:
            headers = page._build_visible_headers()

        page.search_edit = QtWidgets.QLineEdit()
        page.search_edit.setObjectName("SearchBox")
        page.search_edit.setPlaceholderText(page.config.search_placeholder)
        page.search_edit.setMinimumWidth(160)
        page.search_edit.setMaximumWidth(page.config.search_max_width)
        page.search_edit.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Preferred,
            QtWidgets.QSizePolicy.Policy.Fixed,
        )
        page.search_edit.textChanged.connect(lambda _: page._search_timer.start())
        page.search_edit.returnPressed.connect(page.apply_filter)
        page._search_key_filter = _SearchKeyFilter(page)
        page.search_edit.installEventFilter(page._search_key_filter)

        page.board_combo = QtWidgets.QComboBox()
        page.board_combo.setObjectName("BoardCombo")
        page.board_combo.addItems(["全部", "沪深主板", "创业板", "科创板", "北交所"])
        page.board_combo.setVisible(page.config.show_board_filter)
        page.board_combo.currentIndexChanged.connect(page._on_board_changed)

        page.sync_button = QtWidgets.QPushButton("同步 A 股列表", page)
        page.sync_button.clicked.connect(page.sync_universe_clicked)
        page.sync_button.setVisible(page.config.show_sync_button)

        page.download_button = QtWidgets.QPushButton("下载日K到本地", page)
        page.download_button.clicked.connect(page.download_selected)
        page.download_button.setEnabled(False)
        page.download_button.setVisible(page.config.show_download_button)

        page.fill_button = QtWidgets.QPushButton("补全到最新", page)
        page.fill_button.clicked.connect(page.fill_selected)
        page.fill_button.setEnabled(False)
        page.fill_button.setVisible(page.config.show_fill_button)

        page.redownload_button = QtWidgets.QPushButton("重新下载", page)
        page.redownload_button.clicked.connect(page.redownload_selected)
        page.redownload_button.setEnabled(False)
        page.redownload_button.setVisible(page.config.show_redownload_button)

        page.delete_local_button = QtWidgets.QPushButton("删除本地数据", page)
        page.delete_local_button.setObjectName("DangerButton")
        page.delete_local_button.clicked.connect(page.delete_selected_local)
        page.delete_local_button.setEnabled(False)
        page.delete_local_button.hide()

        page.batch_fill_button = QtWidgets.QPushButton("批量补全过期", page)
        page.batch_fill_button.setObjectName("SecondaryButton")
        page.batch_fill_button.clicked.connect(page.batch_fill_stale)
        page.batch_fill_button.setEnabled(False)
        page.batch_fill_button.hide()

        page.batch_gap_fill_button = QtWidgets.QPushButton("批量修复断层", page)
        page.batch_gap_fill_button.setObjectName("SecondaryButton")
        page.batch_gap_fill_button.clicked.connect(page.batch_fill_gaps)
        page.batch_gap_fill_button.setEnabled(False)
        page.batch_gap_fill_button.hide()

        page.gap_fill_button = QtWidgets.QPushButton("修复断层", page)
        page.gap_fill_button.setObjectName("SecondaryButton")
        page.gap_fill_button.clicked.connect(page.fill_selected_gaps)
        page.gap_fill_button.setEnabled(False)
        page.gap_fill_button.hide()

        page.local_period_combo = QtWidgets.QComboBox()
        for label, value in LOCAL_SCOPE_OPTIONS:
            page.local_period_combo.addItem(label, value)
        apply_toolbar_combo_style(page.local_period_combo)
        page.local_period_combo.setVisible(page.config.use_local_table)
        page.local_period_combo.currentIndexChanged.connect(page._on_local_period_changed)

        page.add_watchlist_button = QtWidgets.QPushButton("加入自选", page)
        page.add_watchlist_button.clicked.connect(page._watchlist.add_selected)
        page.add_watchlist_button.setEnabled(False)
        page.add_watchlist_button.setVisible(page.config.show_add_watchlist_button)

        page.remove_watchlist_button = QtWidgets.QPushButton("移出自选", page)
        page.remove_watchlist_button.clicked.connect(page._watchlist.remove_selected)
        page.remove_watchlist_button.setEnabled(False)
        page.remove_watchlist_button.setVisible(page.config.show_remove_watchlist_button)

        page.move_watchlist_up_button = QtWidgets.QPushButton("上移", page)
        page.move_watchlist_up_button.clicked.connect(lambda: page._watchlist.move_selected("up"))
        page.move_watchlist_up_button.setEnabled(False)
        page.move_watchlist_up_button.setVisible(page.config.show_watchlist_move_buttons)

        page.move_watchlist_down_button = QtWidgets.QPushButton("下移", page)
        page.move_watchlist_down_button.clicked.connect(lambda: page._watchlist.move_selected("down"))
        page.move_watchlist_down_button.setEnabled(False)
        page.move_watchlist_down_button.setVisible(page.config.show_watchlist_move_buttons)

        page.backtest_button = QtWidgets.QPushButton("策略回测", page)
        page.backtest_button.setObjectName("SecondaryButton")
        page.backtest_button.clicked.connect(page._actions.open_backtest_for_selected)
        page.backtest_button.setEnabled(False)
        page.backtest_button.setVisible(page.config.show_backtest_button)

        page.batch_backtest_button = QtWidgets.QPushButton("批量回测", page)
        page.batch_backtest_button.setObjectName("SecondaryButton")
        page.batch_backtest_button.clicked.connect(page.run_watchlist_batch_backtest)
        page.batch_backtest_button.setEnabled(False)
        page.batch_backtest_button.setVisible(page.config.show_batch_backtest_button)

        page.refresh_signals_button = QtWidgets.QPushButton("刷新信号", page)
        page.refresh_signals_button.setObjectName("SecondaryButton")
        page.refresh_signals_button.clicked.connect(page.refresh_watchlist_signals)
        page.refresh_signals_button.setVisible(False)

        page.add_signal_panel_button = QtWidgets.QPushButton("加入信号区", page)
        page.add_signal_panel_button.setObjectName("SecondaryButton")
        page.add_signal_panel_button.clicked.connect(page.add_selection_to_signal_panel)
        page.add_signal_panel_button.setVisible(page.config.show_watchlist_signals)

        page.register_position_button = QtWidgets.QPushButton("登记持仓", page)
        page.register_position_button.setObjectName("SecondaryButton")
        page.register_position_button.clicked.connect(page.register_position_for_selected)
        page.register_position_button.setVisible(page.config.show_watchlist_positions)

        page.diagnose_button = QtWidgets.QPushButton("诊断", page)
        page.diagnose_button.clicked.connect(page._actions.run_diagnose_for_selected)
        page.diagnose_button.setEnabled(False)
        page.diagnose_button.setVisible(page.config.show_diagnose_button)

        page.refresh_quotes_button = QtWidgets.QPushButton("刷新行情", page)
        page.refresh_quotes_button.setObjectName("SecondaryButton")
        page.refresh_quotes_button.clicked.connect(page._refresh_quotes_clicked)
        show_quotes_refresh = page.config.use_market_rank or page.config.show_refresh_quotes_button
        page.refresh_quotes_button.setVisible(show_quotes_refresh)
        if page.config.show_refresh_quotes_button and not page.config.use_market_rank:
            page.refresh_quotes_button.setToolTip("强制拉取自选池最新报价（非交易时段也可用）")

        page.market_auto_refresh_checkbox = QtWidgets.QCheckBox("自动刷新行情", page)
        page.market_auto_refresh_checkbox.setVisible(page.config.use_market_rank)
        page._market_auto_refresh = load_market_auto_refresh_pref()
        page.market_auto_refresh_checkbox.blockSignals(True)
        page.market_auto_refresh_checkbox.setChecked(page._market_auto_refresh)
        page.market_auto_refresh_checkbox.blockSignals(False)
        page.market_auto_refresh_checkbox.toggled.connect(page._on_market_auto_refresh_toggled)

        more_actions: list[tuple[str, QtWidgets.QPushButton]] = []

        toolbar = QtWidgets.QHBoxLayout()
        toolbar.setSpacing(8)
        toolbar.addWidget(page.search_edit)
        if page.config.show_board_filter:
            toolbar.addWidget(page.board_combo)

        # ── 分隔线 ──
        group2_visible = page.config.use_market_rank or page.config.show_sync_button
        if group2_visible:
            toolbar.addWidget(_toolbar_separator())

        if page.config.use_market_rank:
            toolbar.addWidget(page.market_auto_refresh_checkbox)
            toolbar.addWidget(page.refresh_quotes_button)
        if page.config.show_sync_button:
            toolbar.addWidget(page.sync_button)

        # ── 分隔线 ──
        group3_visible = (
            page.config.show_add_watchlist_button
            or page.config.show_download_button
            or page.config.show_backtest_button
            or page.config.show_batch_backtest_button
            or page.config.show_fill_button
            or page.config.show_watchlist_move_buttons
        )
        if group2_visible and group3_visible:
            toolbar.addWidget(_toolbar_separator())

        if page.config.use_local_table:
            toolbar.addWidget(page.local_period_combo)
        if page.config.show_add_watchlist_button:
            toolbar.addWidget(page.add_watchlist_button)
        if page.config.show_remove_watchlist_button:
            toolbar.addWidget(page.remove_watchlist_button)
        if page.config.show_watchlist_move_buttons:
            more_actions.extend(
                [
                    ("上移", page.move_watchlist_up_button),
                    ("下移", page.move_watchlist_down_button),
                ]
            )
        # 自选页：下载入口仅在右键菜单；市场页保留工具栏按钮
        if page.config.show_download_button and not page.config.use_local_table:
            if not page.config.show_watchlist_move_buttons:
                toolbar.addWidget(page.download_button)
        elif page.config.show_download_button:
            toolbar.addWidget(page.download_button)
        if page.config.show_fill_button:
            more_actions.append(("补全到最新", page.fill_button))
        if page.config.show_redownload_button:
            more_actions.append(("重新下载", page.redownload_button))
        if page.config.show_delete_button:
            more_actions.append(("删除本地数据", page.delete_local_button))
        if page.config.show_batch_fill_button:
            more_actions.append(("批量补全过期", page.batch_fill_button))
        if page.config.show_batch_gap_fill_button:
            more_actions.append(("修复断层", page.gap_fill_button))
            more_actions.append(("批量修复断层", page.batch_gap_fill_button))
        if page.config.show_backtest_button:
            toolbar.addWidget(page.backtest_button)
        if page.config.show_batch_backtest_button:
            more_actions.append(("批量回测", page.batch_backtest_button))
        if page.config.show_watchlist_signals:
            toolbar.addWidget(page.add_signal_panel_button)
        if page.config.show_watchlist_positions:
            toolbar.addWidget(page.register_position_button)
        if page.config.show_diagnose_button:
            toolbar.addWidget(page.diagnose_button)
        if page.config.show_refresh_quotes_button and not page.config.use_market_rank:
            toolbar.addWidget(page.refresh_quotes_button)
        if page.config.column_configurable:
            page.column_button = QtWidgets.QPushButton("列 ▾")
            page.column_button.setObjectName("SecondaryButton")
            page.column_button.clicked.connect(page._table.show_column_menu)
            toolbar.addWidget(page.column_button)
        _add_more_menu(toolbar, more_actions)
        for _, menu_btn in more_actions:
            menu_btn.hide()
        toolbar.addStretch(1)

        toolbar_host = QtWidgets.QWidget()
        if page.page_name == "市场":
            toolbar_host.setObjectName("MarketToolbar")
            toolbar_margins = (12, 8, 12, 8)
        else:
            toolbar_host.setObjectName("QuotesToolbarHost")
            toolbar_margins = (8, 8, 8, 4)
        toolbar_host_layout = QtWidgets.QVBoxLayout(toolbar_host)
        toolbar_host_layout.setContentsMargins(*toolbar_margins)
        toolbar_host_layout.setSpacing(0)
        toolbar_host_layout.addLayout(toolbar)

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

        page._pagination.set_visible()

        page.stats_label = QtWidgets.QLabel("")
        page.stats_label.setObjectName("StatsLabel")
        page.stats_label.setVisible(page.config.column_configurable)

        page.quote_table_model = QuoteTableModel(page)
        page.quote_table_model.set_headers(headers)
        page.market_table = QtWidgets.QTableView()
        page.market_table.setObjectName("MarketTable")
        page.market_table.setModel(page.quote_table_model)
        page.market_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        if page.config.show_watchlist_signals:
            page.market_table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
        else:
            page.market_table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        page.market_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        page.market_table.verticalHeader().setVisible(False)
        page.market_table.setAlternatingRowColors(True)
        page.market_table.setSortingEnabled(False)
        page.market_table.selectionModel().selectionChanged.connect(page._table.on_selection_changed)
        page.market_table.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        page.market_table.customContextMenuRequested.connect(page._actions.show_context_menu)
        if page.config.table_header_sortable:
            header = page.market_table.horizontalHeader()
            header.setSortIndicatorShown(True)
            header.setSectionsClickable(True)
            if page.config.use_market_rank and page.config.market_full_list:
                header.sectionClicked.connect(page._table.on_market_header_clicked)

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
            theme_manager().bind_stylesheet(chart_frame, extra=build_chart_frame_stylesheet)
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

            chart_row_host = QtWidgets.QWidget()
            chart_row_host.setLayout(chart_row)

            right_content = QtWidgets.QWidget()
            right_content.setObjectName("ChartSideContent")
            right_panel = QtWidgets.QVBoxLayout(right_content)
            right_panel.setContentsMargins(0, 0, 0, 0)
            right_panel.setSpacing(4)
            right_panel.addLayout(quote_info)
            if page.config.column_configurable:
                right_panel.addLayout(page.quote_sub_info)
            if page.config.show_diagnose_panel:
                page.diagnose_panel = DiagnosePanel()
                page.diagnose_panel.refresh_requested.connect(page.run_diagnose_for_selected)
                right_panel.addWidget(page.diagnose_panel)
            right_panel.addWidget(chart_row_host, stretch=1)

            page.chart_section = ChartSectionPanel(page.page_name)
            page.chart_section.set_content(right_content)
            page.chart_section.expansion_changed.connect(page._on_chart_section_expansion_changed)

            splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
            page._splitter = splitter
            center_widget = QtWidgets.QWidget()
            center_layout = QtWidgets.QVBoxLayout(center_widget)
            center_layout.setContentsMargins(0, 0, 0, 0)
            center_layout.addWidget(toolbar_host)
            if page.stats_label is not None:
                center_layout.addWidget(page.stats_label)
            page._market_table_host = MarketTableHost(
                page.market_table,
                external_scrollbar=False,
            )
            use_center_split = page.config.show_watchlist_signals or page.config.show_watchlist_positions or page.config.show_run_output_panel
            if use_center_split:
                center_split = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
                configure_center_splitter(center_split)
                center_split.addWidget(page._market_table_host)
                split_index = 1
                if page.config.show_watchlist_signals:
                    page.signal_panel = WatchlistSignalPanel(page)
                    center_split.addWidget(page.signal_panel)
                    split_index += 1
                if page.config.show_watchlist_positions:
                    page.position_panel = WatchlistPositionPanel(page)
                    center_split.addWidget(page.position_panel)
                    split_index += 1
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
                    page.run_output_panel.expansion_changed.connect(lambda expanded: on_run_output_expansion_changed(page, expanded))
                    center_split.addWidget(page.run_output_panel)
                page._center_splitter = center_split
                page._run_output_splitter = center_split
                center_layout.addWidget(center_split, stretch=1)
                bind_center_splitter_persistence(page)
                QtCore.QTimer.singleShot(0, lambda: restore_center_splitter(page))
            else:
                center_layout.addWidget(page._market_table_host, stretch=1)
            if page.config.show_watchlist_signals:
                page._wire_signal_panel()
            if page.config.show_watchlist_positions:
                page._wire_position_panel()
            splitter.addWidget(center_widget)

            page._right_panel_widget = page.chart_section
            splitter.addWidget(page.chart_section)
            from vnpy_ashare.ui.quotes.chart.section import (
                chart_side_expanded_min_width,
                sync_chart_splitter_for_expansion,
            )

            page.chart_section.setMinimumWidth(chart_side_expanded_min_width(page))
            if not page.chart_section.is_expanded():
                QtCore.QTimer.singleShot(
                    0,
                    lambda: sync_chart_splitter_for_expansion(page, False),
                )
            splitter.setStretchFactor(0, 3)
            splitter.setStretchFactor(1, 2)
        else:
            # 市场页：单栏全宽布局
            center_widget = QtWidgets.QWidget()
            center_widget.setObjectName("MarketContent")
            center_layout = QtWidgets.QVBoxLayout(center_widget)
            center_layout.setContentsMargins(0, 0, 0, 0)
            center_layout.setSpacing(0)
            center_layout.addWidget(toolbar_host)
            if page.stats_label is not None and page.stats_label.isVisible():
                center_layout.addWidget(page.stats_label)
            page._market_table_host = MarketTableHost(page.market_table)
            center_layout.addWidget(page._market_table_host, stretch=1)

            main_content = center_widget
            if page.config.show_rank_sidebar:
                from vnpy_ashare.ui.quotes.features.market_rank_sidebar import (
                    MarketRankSidebar,
                    sync_rank_splitter_for_expansion,
                )

                page.rank_sidebar = MarketRankSidebar(page)
                page.rank_list = page.rank_sidebar.rank_list
                page.rank_list.currentRowChanged.connect(page._on_rank_type_changed)
                rank_splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
                rank_splitter.setObjectName("MarketRankSplitter")
                rank_splitter.addWidget(page.rank_sidebar)
                rank_splitter.addWidget(center_widget)
                rank_splitter.setStretchFactor(0, 0)
                rank_splitter.setStretchFactor(1, 1)
                rank_splitter.setHandleWidth(1)
                page._rank_splitter = rank_splitter
                page.rank_sidebar.expansion_changed.connect(
                    lambda expanded: sync_rank_splitter_for_expansion(page, expanded)
                )
                main_content = rank_splitter
                page._init_rank_sidebar_selection()
                QtCore.QTimer.singleShot(
                    0,
                    lambda: sync_rank_splitter_for_expansion(page, page.rank_sidebar.is_expanded()),
                )

            splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
            splitter.addWidget(main_content)

        page.status_label = QtWidgets.QLabel("就绪")
        page.quote_source_label = QtWidgets.QLabel(
            quote_source_label(
                page.config,
                gateway_active=is_gateway_quote_active(),
            )
        )
        page.quote_source_label.setObjectName("BottomBarMeta")
        page.refresh_hint_label = QtWidgets.QLabel("")
        page._update_refresh_hint_label()
        page.refresh_hint_label.setObjectName("BottomBarMeta")

        bottom_bar = QtWidgets.QHBoxLayout()
        bottom_bar.setContentsMargins(8, 2, 8, 4)
        bottom_bar.addWidget(page.status_label, stretch=1)
        bottom_bar.addWidget(page.quote_source_label)
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
        page._toast = PageToastHost(page)
        root.addWidget(page._toast)

    def _build_radar_layout(self, page: QuotesPage) -> None:
        from vnpy_ashare.ui.quotes.page.config import (
            RADAR_REFRESH_INTERVAL_OPTIONS,
            load_radar_auto_refresh_pref,
            load_radar_refresh_interval_ms,
        )
        from vnpy_ashare.ui.quotes.radar import RadarBoard, RadarController, RadarResonancePanel

        page.refresh_radar_button = QtWidgets.QPushButton("刷新雷达", page)
        page.radar_ai_button = QtWidgets.QPushButton("AI 洞察", page)

        page.market_auto_refresh_checkbox = QtWidgets.QCheckBox("自动刷新", page)
        page._radar_auto_refresh = load_radar_auto_refresh_pref()
        page._radar_refresh_interval_ms = load_radar_refresh_interval_ms()
        page.market_auto_refresh_checkbox.blockSignals(True)
        page.market_auto_refresh_checkbox.setChecked(page._radar_auto_refresh)
        page.market_auto_refresh_checkbox.blockSignals(False)
        page.market_auto_refresh_checkbox.toggled.connect(page._on_market_auto_refresh_toggled)

        page.radar_refresh_interval_combo = QtWidgets.QComboBox(page)
        page.radar_refresh_interval_combo.setObjectName("ToolbarCombo")
        saved_interval = page._radar_refresh_interval_ms
        for interval_ms, label in RADAR_REFRESH_INTERVAL_OPTIONS:
            page.radar_refresh_interval_combo.addItem(label, interval_ms)
        saved_index = page.radar_refresh_interval_combo.findData(saved_interval)
        if saved_index >= 0:
            page.radar_refresh_interval_combo.setCurrentIndex(saved_index)
        page.radar_refresh_interval_combo.currentIndexChanged.connect(page._on_radar_refresh_interval_changed)
        page.radar_refresh_interval_combo.setEnabled(page._radar_auto_refresh)

        toolbar = QtWidgets.QHBoxLayout()
        toolbar.setSpacing(8)
        toolbar.addWidget(page.market_auto_refresh_checkbox)
        toolbar.addWidget(page.radar_refresh_interval_combo)
        toolbar.addWidget(page.refresh_radar_button)
        toolbar.addWidget(page.radar_ai_button)
        toolbar.addStretch(1)

        toolbar_host = QtWidgets.QWidget()
        toolbar_host.setObjectName("QuotesToolbarHost")
        toolbar_host_layout = QtWidgets.QVBoxLayout(toolbar_host)
        toolbar_host_layout.setContentsMargins(8, 8, 8, 4)
        toolbar_host_layout.setSpacing(0)
        toolbar_host_layout.addLayout(toolbar)

        page.radar_board = RadarBoard(page)
        page.radar_resonance_panel = RadarResonancePanel(page)
        from vnpy_common.ui.theme.build_extra import build_radar_stylesheet

        theme_manager().bind_stylesheet(page.radar_board, extra=build_radar_stylesheet)
        theme_manager().bind_stylesheet(page.radar_resonance_panel, extra=build_radar_stylesheet)
        page._radar_controller = RadarController(
            page,
            page.radar_board,
            resonance_panel=page.radar_resonance_panel,
        )
        page.refresh_radar_button.clicked.connect(page._radar_controller.refresh)
        page.radar_ai_button.clicked.connect(page._radar_controller.request_ai_summary)

        center = QtWidgets.QWidget()
        center_layout = QtWidgets.QVBoxLayout(center)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(0)
        center_layout.addWidget(toolbar_host)
        center_layout.addWidget(page.radar_board, stretch=1)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        splitter.setObjectName("RadarMainSplitter")
        splitter.addWidget(center)
        splitter.addWidget(page.radar_resonance_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)
        splitter.setSizes([900, 260])
        page._radar_splitter = splitter

        page.status_label = QtWidgets.QLabel("就绪")
        page.quote_source_label = QtWidgets.QLabel(
            quote_source_label(page.config, gateway_active=is_gateway_quote_active()),
        )
        page.quote_source_label.setObjectName("BottomBarMeta")
        page.refresh_hint_label = QtWidgets.QLabel("")
        page._update_refresh_hint_label()
        page.refresh_hint_label.setObjectName("BottomBarMeta")

        bottom_bar = QtWidgets.QHBoxLayout()
        bottom_bar.setContentsMargins(8, 2, 8, 4)
        bottom_bar.addWidget(page.status_label, stretch=1)
        bottom_bar.addWidget(page.quote_source_label)
        bottom_bar.addStretch()
        bottom_bar.addWidget(page.refresh_hint_label)

        root = QtWidgets.QVBoxLayout(page)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(splitter, stretch=1)
        root.addLayout(bottom_bar)
        page._toast = PageToastHost(page)
        root.addWidget(page._toast)


class _SearchKeyFilter(QtCore.QObject):
    """搜索框 Enter 立即过滤、Esc 清空。"""

    def __init__(self, page: QuotesPage) -> None:
        super().__init__(page)
        self._page = page

    def eventFilter(self, watched: QtCore.QObject, event: QtCore.QEvent) -> bool:
        if watched is not self._page.search_edit:
            return super().eventFilter(watched, event)
        if event.type() != QtCore.QEvent.Type.KeyPress:
            return super().eventFilter(watched, event)
        key = event.key()
        if key == QtCore.Qt.Key.Key_Escape:
            self._page.search_edit.clear()
            self._page._search_timer.stop()
            self._page.apply_filter()
            return True
        if key in (QtCore.Qt.Key.Key_Return, QtCore.Qt.Key.Key_Enter):
            self._page._search_timer.stop()
            self._page.apply_filter()
            return True
        return super().eventFilter(watched, event)
