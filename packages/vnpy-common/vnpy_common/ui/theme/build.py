"""由 ThemeTokens 生成终端 QSS。"""

from __future__ import annotations

from functools import lru_cache

from vnpy_common.ui.theme.build_loading import build_content_loading_stylesheet
from vnpy_common.ui.theme.build_panel import build_panel_stylesheet
from vnpy_common.ui.theme.build_screener import build_screener_stylesheet
from vnpy_common.ui.theme.build_scrollbar import (
    build_market_table_scrollbar_stylesheet,
    build_terminal_scrollbar_stylesheet,
)
from vnpy_common.ui.theme.build_table import build_data_table_stylesheet
from vnpy_common.ui.theme.tokens import ThemeId, ThemeTokens, get_tokens


def build_terminal_stylesheet(tokens: ThemeTokens) -> str:
    t = tokens
    return _build_global_base(t) + _build_menu_styles(t) + _build_terminal_base(t) + _build_toolbar_combo(t) + build_screener_stylesheet(t)


@lru_cache(maxsize=8)
def cached_terminal_stylesheet(theme_id: ThemeId) -> str:
    """按已解析主题 id 缓存全局 QSS，避免重复拼接。"""
    return build_terminal_stylesheet(get_tokens(theme_id))


def stylesheet_for(theme: ThemeId) -> str:
    return cached_terminal_stylesheet(theme)


def _build_global_base(t: ThemeTokens) -> str:
    return (
        f"""
QWidget {{
    color: {t.text_primary};
    background-color: {t.app_bg};
}}
QMainWindow,
QDialog {{
    background-color: {t.app_bg};
}}
QWidget#MarketRoot,
QStackedWidget,
QStackedWidget#MainStack {{
    background-color: {t.app_bg};
}}
QSplitter {{
    background-color: {t.app_bg};
}}
QWidget#NavBody,
QWidget#QuotesToolbarHost,
QWidget#AiQuickActionChips,
QWidget#AiInputRow,
QWidget#AiSessionList,
QWidget#TaskRunOutputPanel,
QFrame#ScreenerRunRow,
QFrame#ToolbarSeparator {{
    background-color: transparent;
}}
QLabel {{
    background-color: transparent;
}}
QAbstractScrollArea::viewport {{
    background-color: {t.app_bg};
}}
QScrollArea {{
    background-color: transparent;
    border: none;
}}
QLineEdit,
QSpinBox,
QDoubleSpinBox,
QDateEdit,
QDateTimeEdit,
QTimeEdit {{
    background-color: {t.input_bg};
    color: {t.input_text};
    border: 1px solid {t.input_border};
    border-radius: 4px;
    padding: 4px 8px;
    selection-background-color: {t.table_selected};
    selection-color: {t.text_primary};
}}
QLineEdit:focus,
QSpinBox:focus,
QDoubleSpinBox:focus,
QDateEdit:focus {{
    border-color: {t.accent};
}}
QComboBox {{
    background-color: {t.combo_bg};
    color: {t.combo_text};
    border: 1px solid {t.combo_border};
    border-radius: 4px;
    padding: 4px 8px;
    padding-right: 24px;
}}
QComboBox:hover {{
    background-color: {t.combo_hover_bg};
    border-color: {t.combo_hover_border};
}}
QComboBox:disabled {{
    background-color: {t.combo_disabled_bg};
    color: {t.combo_disabled_text};
}}
QComboBox::drop-down {{
    border: none;
    width: 20px;
}}
QComboBox QAbstractItemView {{
    background-color: {t.combo_popup_bg};
    color: {t.combo_text};
    border: 1px solid {t.combo_popup_border};
    selection-background-color: {t.combo_selection_bg};
    selection-color: {t.text_primary};
    outline: none;
}}
QTextEdit,
QPlainTextEdit {{
    background-color: {t.input_bg};
    color: {t.input_text};
    border: 1px solid {t.input_border};
    selection-background-color: {t.table_selected};
    selection-color: {t.text_primary};
}}
QTableWidget,
QTreeWidget,
QListWidget,
QTableView,
QTreeView,
QListView {{
    background-color: {t.table_bg};
    color: {t.text_primary};
    gridline-color: {t.table_grid};
    alternate-background-color: {t.table_alt};
    selection-background-color: {t.table_selected};
    selection-color: {t.text_primary};
    border: none;
}}
QHeaderView::section {{
    background-color: {t.header_bg};
    color: {t.header_text};
    padding: 6px 8px;
    border: none;
    border-right: 1px solid {t.header_border};
    border-bottom: 1px solid {t.header_border};
}}
QGroupBox {{
    background-color: {t.panel_bg};
    color: {t.text_secondary};
    border: 1px solid {t.panel_border};
    border-radius: 6px;
    margin-top: 12px;
    padding: 12px;
}}
QTabWidget::pane {{
    border: 1px solid {t.panel_border};
    background-color: {t.panel_bg};
    top: -1px;
}}
QTabBar::tab {{
    background-color: {t.tab_bg};
    color: {t.tab_text};
    border: 1px solid {t.tab_border};
    border-bottom: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    padding: 5px 12px;
    margin-right: 2px;
}}
QTabBar::tab:selected {{
    background-color: {t.tab_selected_bg};
    color: {t.tab_selected_text};
}}
QTabBar::tab:hover {{
    color: {t.tab_hover_text};
}}
QCheckBox,
QRadioButton {{
    color: {t.text_primary};
    background-color: transparent;
}}
QCheckBox::indicator {{
    width: 14px;
    height: 14px;
    border: 1px solid {t.checkbox_border};
    border-radius: 3px;
    background-color: {t.checkbox_bg};
}}
QCheckBox::indicator:checked {{
    background-color: {t.accent};
    border-color: {t.accent};
}}
QToolTip {{
    background-color: {t.panel_bg};
    color: {t.text_primary};
    border: 1px solid {t.panel_border};
    padding: 4px 8px;
}}
QStatusBar {{
    background-color: {t.statusbar_bg};
    color: {t.statusbar_text};
    border-top: 1px solid {t.statusbar_border};
}}
QScrollBar:vertical {{
    background: {t.panel_bg};
    width: 10px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {t.splitter_handle};
    min-height: 24px;
    border-radius: 4px;
}}
QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {{
    height: 0;
}}
"""
        + build_terminal_scrollbar_stylesheet(t)
        + build_market_table_scrollbar_stylesheet(t)
        + build_content_loading_stylesheet(t)
        + build_panel_stylesheet(t)
        + build_data_table_stylesheet(t)
        + f"""
QScrollBar:horizontal {{
    background: {t.panel_bg};
    height: 10px;
    margin: 0;
}}
QScrollBar::handle:horizontal {{
    background: {t.splitter_handle};
    min-width: 24px;
    border-radius: 4px;
}}
QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal {{
    width: 0;
}}
QWidget#ScreenerFormPanel {{
    background-color: {t.screener_form_bg};
    border: 1px solid {t.screener_form_border};
    border-radius: 6px;
}}
QWidget#ChartPanel,
QWidget#ChartFrame {{
    background-color: {t.depth_bg};
}}
QLabel#ChartHint {{
    color: {t.text_muted};
    font-size: 12px;
    padding: 4px 8px;
}}
QWidget#MaLegendBar {{
    background-color: {t.app_bg};
    border-bottom: 1px solid {t.table_grid};
}}
QPlainTextEdit#ScreenerRunLogView,
QPlainTextEdit#TaskRunLogView {{
    background-color: {t.screener_log_bg};
    border: 1px solid {t.screener_log_border};
    border-radius: 4px;
    color: {t.screener_log_text};
    font-family: Menlo, Monaco, "Courier New", monospace;
    font-size: 11px;
    padding: 8px 10px;
}}
QLabel#TaskSectionLabel {{
    color: {t.text_section_alt};
    font-size: 12px;
    font-weight: bold;
}}
QLabel#TaskRunSummary {{
    color: {t.text_section_alt};
    font-size: 12px;
}}
"""
    )


def _build_menu_styles(t: ThemeTokens) -> str:
    return f"""
QMenuBar {{
    background-color: {t.menu_bg};
    color: {t.menu_text};
    border-bottom: 1px solid {t.menu_border};
    padding: 2px 0;
}}
QMenuBar::item {{
    background: transparent;
    padding: 4px 10px;
}}
QMenuBar::item:selected {{
    background-color: {t.menu_selected_bg};
    color: {t.menu_selected_text};
}}
QMenu {{
    background-color: {t.menu_bg};
    color: {t.menu_text};
    border: 1px solid {t.menu_border};
}}
QMenu::item {{
    padding: 6px 24px 6px 12px;
}}
QMenu::item:selected {{
    background-color: {t.menu_selected_bg};
    color: {t.menu_selected_text};
}}
"""


def _build_terminal_base(t: ThemeTokens) -> str:
    return f"""
QWidget#MarketRoot {{
    background-color: {t.app_bg};
}}
QWidget#SidebarNav {{
    background-color: {t.nav_bg};
    border-right: none;
}}
QSplitter#MainNavSplitter {{
    background-color: {t.nav_bg};
}}
QSplitter#MainNavSplitter::handle {{
    background-color: {t.splitter_handle};
}}
QSplitter#MainNavSplitter::handle:hover {{
    background-color: {t.accent};
}}
QScrollArea#NavScroll {{
    background-color: {t.nav_bg};
    border: none;
}}
QToolButton#NavButton {{
    background-color: transparent;
    border: none;
    border-radius: 6px;
    color: {t.nav_text};
    padding: 10px 4px;
    margin: 2px 6px;
    font-size: 12px;
}}
QToolButton#NavButton:hover {{
    background-color: {t.nav_hover_bg};
    color: {t.nav_text_hover};
}}
QToolButton#NavButton:checked {{
    background-color: {t.nav_selected_bg};
    color: {t.accent};
}}
QWidget#NavBody {{
    background-color: transparent;
}}
QWidget#NavGroupSpacer {{
    background-color: transparent;
    margin: 2px 0;
}}
QTableWidget#MarketTable,
QTableView#MarketTable,
QTableWidget#ScreenerResultsTable,
QTableView#ScreenerResultsTable,
QTableWidget#BatchCompareTable,
QTableView#BatchCompareTable {{
    background-color: {t.table_bg};
    gridline-color: {t.table_grid};
    border: none;
    font-size: 12px;
    color: {t.text_primary};
    alternate-background-color: {t.table_alt};
    selection-background-color: {t.table_selected};
    selection-color: {t.text_primary};
}}
QHeaderView::section {{
    background-color: {t.header_bg};
    color: {t.header_text};
    padding: 6px 4px;
    border: none;
    border-right: 1px solid {t.header_border};
    font-size: 12px;
}}
QLineEdit#SearchBox {{
    background-color: {t.input_bg};
    border: 1px solid {t.input_border};
    border-radius: 4px;
    padding: 6px 10px;
    color: {t.input_text};
}}
QLabel#QuoteHeader {{
    font-size: 22px;
    font-weight: bold;
    color: {t.text_primary};
}}
QLabel#IndexTicker {{
    background-color: {t.index_ticker_bg};
    color: {t.index_ticker_text};
    padding: 6px 12px;
    font-size: 12px;
}}
QPushButton {{
    background-color: {t.btn_bg};
    border: 1px solid {t.btn_border};
    border-radius: 4px;
    padding: 6px 14px;
    color: {t.btn_text};
}}
QPushButton:hover {{
    background-color: {t.btn_hover_bg};
}}
QPushButton:disabled {{
    color: {t.btn_disabled_text};
}}
QPushButton#ActionButton {{
    background-color: {t.action_btn_bg};
    border: 1px solid {t.action_btn_border};
    border-radius: 4px;
    padding: 4px 14px;
    color: {t.action_btn_text};
    font-weight: bold;
    font-size: 12px;
}}
QPushButton#ActionButton:hover {{
    background-color: {t.action_btn_hover_bg};
    border-color: {t.action_btn_hover_border};
}}
QPushButton#ActionButton:pressed {{
    background-color: {t.action_btn_pressed_bg};
}}
QPushButton#SecondaryButton {{
    background-color: {t.secondary_btn_bg};
    border: 1px solid {t.secondary_btn_border};
    border-radius: 4px;
    padding: 4px 14px;
    color: {t.secondary_btn_text};
    font-size: 12px;
}}
QPushButton#SecondaryButton:hover {{
    background-color: {t.secondary_btn_hover_bg};
    border-color: {t.secondary_btn_hover_border};
    color: {t.secondary_btn_hover_text};
}}
QPushButton#SecondaryButton:pressed {{
    background-color: {t.secondary_btn_pressed_bg};
}}
QPushButton#DangerButton {{
    background-color: {t.danger_btn_bg};
    border: 1px solid {t.danger_btn_border};
    border-radius: 4px;
    padding: 4px 14px;
    color: {t.danger_btn_text};
    font-size: 12px;
}}
QPushButton#DangerButton:hover {{
    background-color: {t.danger_btn_hover_bg};
    border-color: {t.danger_btn_hover_border};
    color: {t.danger_btn_hover_text};
}}
QLabel#PageTitle {{
    color: {t.text_primary};
    font-size: 16px;
    font-weight: 600;
}}
QLabel#PageHint {{
    color: {t.text_muted};
    font-size: 12px;
}}
QLabel#BottomBarMeta {{
    color: {t.text_secondary};
    font-size: 12px;
}}
QLabel#StatsLabel,
QLabel#QuoteSubInfo {{
    color: {t.text_secondary};
    font-size: 12px;
    padding: 2px 6px;
}}
QWidget#WatchlistSignalPanel {{
    background-color: {t.app_bg};
    border-top: 1px solid {t.table_grid};
}}
QTableWidget#WatchlistSignalTable {{
    background-color: {t.table_bg};
    border: 1px solid {t.table_grid};
    border-radius: 4px;
    gridline-color: {t.table_grid};
}}
QWidget#QuotesToolbarHost {{
    background-color: transparent;
}}
QFrame#DepthPanel {{
    background-color: {t.depth_bg};
    border: 1px solid {t.table_grid};
    border-radius: 4px;
}}
QFrame#DepthPanel QLabel {{
    color: {t.depth_text};
    font-size: 12px;
}}
QFrame#DepthPanel QTableWidget,
QFrame#DepthPanel QTableWidget#DepthTable {{
    background-color: {t.depth_table_bg};
    border: none;
    font-size: 12px;
    color: {t.depth_table_text};
}}
QWidget#DiagnosePanel {{
    background-color: {t.diagnose_bg};
    border: 1px solid {t.diagnose_border};
    border-radius: 6px;
    padding: 4px;
}}
QLabel#SectionLabel {{
    color: {t.text_section};
    font-size: 12px;
    font-weight: bold;
}}
QLabel#DiagnoseBody {{
    color: {t.text_secondary};
    font-size: 12px;
}}
QLabel#AiSessionTitle {{
    color: {t.text_primary};
    font-size: 13px;
    font-weight: bold;
}}
"""


def _build_toolbar_combo(t: ThemeTokens) -> str:
    return f"""
QComboBox#ToolbarCombo {{
    background-color: {t.combo_bg};
    border: 1px solid {t.combo_border};
    border-radius: 4px;
    color: {t.combo_text};
    padding: 6px 10px;
    padding-right: 26px;
    font-size: 13px;
    min-width: 76px;
}}
QComboBox#ToolbarCombo:hover {{
    border-color: {t.combo_hover_border};
    background-color: {t.combo_hover_bg};
}}
QComboBox#ToolbarCombo:focus {{
    border-color: {t.accent};
}}
QComboBox#ToolbarCombo:disabled {{
    color: {t.combo_disabled_text};
    background-color: {t.combo_disabled_bg};
}}
QComboBox#ToolbarCombo::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: center right;
    width: 22px;
    border: none;
}}
QComboBox#ToolbarCombo::down-arrow {{
    width: 10px;
    height: 10px;
}}
QComboBox#ToolbarCombo QAbstractItemView {{
    background-color: {t.combo_popup_bg};
    color: {t.combo_text};
    border: 1px solid {t.combo_popup_border};
    selection-background-color: {t.combo_selection_bg};
    selection-color: {t.action_btn_text};
    outline: none;
    padding: 4px 0;
}}
QComboBox#ToolbarCombo QAbstractItemView::item {{
    min-height: 32px;
    padding: 6px 14px;
    color: {t.combo_text};
}}
QComboBox#ToolbarCombo QAbstractItemView::item:hover {{
    background-color: {t.combo_item_hover_bg};
    color: {t.text_primary};
}}
QComboBox#ToolbarCombo QAbstractItemView::item:selected {{
    background-color: {t.combo_selection_bg};
    color: {t.action_btn_text};
}}
"""
