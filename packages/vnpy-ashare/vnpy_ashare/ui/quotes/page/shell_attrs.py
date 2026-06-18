"""QuotesPage 由 shell 赋值的 UI 属性类型（mixin，仅作 mypy 声明）。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.ui.components.task_run_output_panel import TaskRunOutputPanel
from vnpy_ashare.ui.quotes.chart.panel import ChartPanel
from vnpy_ashare.ui.quotes.chart.section import ChartSectionPanel
from vnpy_ashare.ui.quotes.panels.depth import DepthPanel
from vnpy_ashare.ui.quotes.panels.diagnose import DiagnosePanel
from vnpy_ashare.ui.quotes.panels.loading_overlay import MarketTableHost
from vnpy_ashare.ui.quotes.table.model import QuoteTableModel

if TYPE_CHECKING:
    from vnpy_ashare.ui.quotes.chart.daily import AshareChartWidget
    from vnpy_ashare.ui.quotes.features.market_rank_sidebar import (
        MarketRankSidebar,
        MarketRankSplitterResizeFilter,
    )
    from vnpy_ashare.ui.quotes.market_overview.emotion_cycle_chip import EmotionCycleChip
    from vnpy_ashare.ui.quotes.market_overview.industry_filter_combo import IndustryFilterCombo
    from vnpy_ashare.ui.quotes.radar.card import RadarBoard
    from vnpy_ashare.ui.quotes.radar.controller import RadarController
    from vnpy_ashare.ui.quotes.radar.resonance_panel import RadarResonancePanel
    from vnpy_ashare.ui.quotes.stock_notes.panel import StockNotePanel
    from vnpy_ashare.ui.quotes.watchlist_groups.tab_bar import WatchlistGroupTabBar
    from vnpy_ashare.ui.quotes.watchlist_multiview.panel import WatchlistMultiViewBoard
    from vnpy_ashare.ui.quotes.watchlist_positions.panel import WatchlistPositionPanel
    from vnpy_ashare.ui.quotes.watchlist_signals.panel import WatchlistSignalPanel
    from vnpy_common.ui.feedback import PageToastHost


class QuotesPageShellAttrs:
    """Shell 构建后挂载到 QuotesPage 的控件与布局引用。"""

    quote_table_model: QuoteTableModel
    market_table: QtWidgets.QTableView

    search_edit: QtWidgets.QLineEdit
    _search_key_filter: QtCore.QObject
    board_combo: QtWidgets.QComboBox
    industry_filter: IndustryFilterCombo | None
    sync_button: QtWidgets.QPushButton
    download_button: QtWidgets.QPushButton
    fill_button: QtWidgets.QPushButton
    redownload_button: QtWidgets.QPushButton
    delete_local_button: QtWidgets.QPushButton
    batch_fill_button: QtWidgets.QPushButton
    batch_gap_fill_button: QtWidgets.QPushButton
    gap_fill_button: QtWidgets.QPushButton
    local_period_combo: QtWidgets.QComboBox
    add_watchlist_button: QtWidgets.QPushButton
    remove_watchlist_button: QtWidgets.QPushButton
    move_watchlist_up_button: QtWidgets.QPushButton
    move_watchlist_down_button: QtWidgets.QPushButton
    backtest_button: QtWidgets.QPushButton
    batch_backtest_button: QtWidgets.QPushButton
    refresh_signals_button: QtWidgets.QPushButton
    add_signal_panel_button: QtWidgets.QPushButton
    register_position_button: QtWidgets.QPushButton
    quick_note_button: QtWidgets.QPushButton
    notes_center_button: QtWidgets.QPushButton
    diagnose_button: QtWidgets.QPushButton
    refresh_quotes_button: QtWidgets.QPushButton
    market_auto_refresh_checkbox: QtWidgets.QCheckBox
    column_button: QtWidgets.QPushButton | None
    prev_page_button: QtWidgets.QPushButton
    next_page_button: QtWidgets.QPushButton
    page_label: QtWidgets.QLabel
    page_total_label: QtWidgets.QLabel
    home_button: QtWidgets.QPushButton
    end_button: QtWidgets.QPushButton
    page_jump_input: QtWidgets.QLineEdit
    quote_name_label: QtWidgets.QLabel
    quote_code_label: QtWidgets.QLabel
    quote_price_label: QtWidgets.QLabel
    quote_change_label: QtWidgets.QLabel
    quote_sub_info: QtWidgets.QHBoxLayout
    status_label: QtWidgets.QLabel
    quote_source_label: QtWidgets.QLabel
    refresh_hint_label: QtWidgets.QLabel
    emotion_cycle_chip: EmotionCycleChip | None
    _toast: PageToastHost

    chart_panel: ChartPanel | None
    chart_section: ChartSectionPanel | None
    chart: AshareChartWidget | None
    depth_panel: DepthPanel | None
    diagnose_panel: DiagnosePanel | None
    stock_note_panel: StockNotePanel | None
    signal_panel: WatchlistSignalPanel | None
    position_panel: WatchlistPositionPanel | None
    multiview_board: WatchlistMultiViewBoard | None
    watchlist_group_tab_bar: WatchlistGroupTabBar | None
    view_table_button: QtWidgets.QPushButton | None
    view_multiview_button: QtWidgets.QPushButton | None
    run_output_panel: TaskRunOutputPanel | None
    rank_sidebar: MarketRankSidebar | None
    rank_list: QtWidgets.QListWidget | None

    refresh_radar_button: QtWidgets.QPushButton | None
    refresh_radar_all_button: QtWidgets.QPushButton | None
    radar_ai_button: QtWidgets.QPushButton | None
    radar_board: RadarBoard | None
    radar_resonance_panel: RadarResonancePanel | None
    _radar_controller: RadarController | None
    _radar_splitter: QtWidgets.QSplitter | None

    _market_table_host: MarketTableHost | None
    _center_view_stack: QtWidgets.QStackedWidget | None
    _splitter: QtWidgets.QSplitter | None
    _center_splitter: QtWidgets.QSplitter | None
    _right_panel_widget: QtWidgets.QWidget | None
    _rank_splitter: QtWidgets.QSplitter | None
    _rank_splitter_filter: MarketRankSplitterResizeFilter | None

    _market_sort_column: str | None
    _market_sort_ascending: bool
    _center_splitter_bound: bool
