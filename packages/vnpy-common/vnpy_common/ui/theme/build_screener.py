"""选股页 / 自动选股 QSS（ThemeTokens 驱动）。"""

from __future__ import annotations

from vnpy_common.ui.monospace_font import monospace_font_css_stack
from vnpy_common.ui.theme.tokens import ThemeTokens


def build_screener_stylesheet(tokens: ThemeTokens) -> str:
    t = tokens
    return f"""
QFrame#ToolbarSeparator {{
    color: {t.toolbar_sep};
    background-color: {t.toolbar_sep};
    max-width: 1px;
    min-width: 1px;
    margin: 2px 6px;
}}
QGroupBox#ScreenerFormBox {{
    background-color: {t.screener_form_bg};
    border: 1px solid {t.screener_form_border};
    border-radius: 6px;
    margin-top: 16px;
    padding: 14px 14px 10px 14px;
    font-size: 12px;
    color: {t.screener_form_text};
}}
QGroupBox#ScreenerFormBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 6px;
    left: 12px;
    color: {t.text_section};
}}
QLabel#ScreenerSectionLabel {{
    color: {t.text_section_alt};
    font-size: 11px;
    font-weight: bold;
    text-transform: uppercase;
    letter-spacing: 1px;
    padding: 4px 0 2px 0;
}}
QToolButton#ScreenerConfigSectionToggle {{
    border: none;
    padding: 2px;
    min-width: 16px;
    min-height: 16px;
}}
QWidget#ScreenerConfigSection {{
    background: transparent;
}}
QWidget#ScreenerResultActionBar {{
    background: transparent;
}}
QWidget#ScreenerResultInsights {{
    background: transparent;
}}
QWidget#ScreenerResultInsightsContent {{
    background: transparent;
}}
QScrollArea#ScreenerFormScroll {{
    background: transparent;
    border: none;
}}
QLabel#ScreenerHint {{
    color: {t.text_muted};
    font-size: 11px;
    padding: 6px 4px;
}}
QLabel#ResultSummary {{
    color: {t.text_section_alt};
    font-size: 12px;
    padding: 6px 2px;
}}
QLabel#ScreenerEmptyResult {{
    color: {t.text_hint};
    font-size: 13px;
    padding: 24px;
}}
QLabel#ScreenerRunSummary {{
    color: {t.text_section_alt};
    font-size: 12px;
    padding: 4px 2px;
    line-height: 1.4;
}}
QPlainTextEdit#ScreenerRunLogView {{
    background-color: {t.screener_log_bg};
    border: 1px solid {t.screener_log_border};
    border-radius: 4px;
    color: {t.screener_log_text};
    font-family: {monospace_font_css_stack()};
    font-size: 11px;
    padding: 8px 10px;
}}
QStatusBar#ScreenerStatusBar {{
    background-color: {t.statusbar_bg};
    border-top: 1px solid {t.statusbar_border};
    color: {t.statusbar_text};
    font-size: 12px;
    min-height: 28px;
}}
QLabel#PageTaskLabel {{
    color: {t.text_secondary};
    font-size: 12px;
}}
QProgressBar#PageTaskProgress {{
    background-color: {t.input_bg};
    border: 1px solid {t.input_border};
    border-radius: 3px;
    max-height: 14px;
}}
QProgressBar#PageTaskProgress::chunk {{
    background-color: {t.accent};
    border-radius: 2px;
}}
QTableWidget#MarketTable::item,
QTableView#MarketTable::item {{
    padding: 6px 8px;
}}
QTableWidget#ScreenerResultsTable::item,
QTableView#ScreenerResultsTable::item,
QTableWidget#BatchCompareTable::item,
QTableView#BatchCompareTable::item {{
    padding: 0 8px;
    border: none;
}}
QTableWidget#ScreenerResultsTable QHeaderView::section,
QTableView#ScreenerResultsTable QHeaderView::section,
QTableWidget#BatchCompareTable QHeaderView::section,
QTableView#BatchCompareTable QHeaderView::section {{
    padding: 7px 8px;
    border-bottom: 1px solid {t.header_border};
    font-weight: 600;
}}
QTableWidget#MarketTable::item:selected,
QTableView#MarketTable::item:selected,
QTableWidget#MarketTable::item:selected:active,
QTableView#MarketTable::item:selected:active,
QTableWidget#MarketTable::item:selected:!active,
QTableView#MarketTable::item:selected:!active,
QTableWidget#ScreenerResultsTable::item:selected,
QTableView#ScreenerResultsTable::item:selected,
QTableWidget#ScreenerResultsTable::item:selected:active,
QTableView#ScreenerResultsTable::item:selected:active,
QTableWidget#ScreenerResultsTable::item:selected:!active,
QTableView#ScreenerResultsTable::item:selected:!active,
QTableWidget#BatchCompareTable::item:selected,
QTableView#BatchCompareTable::item:selected,
QTableWidget#BatchCompareTable::item:selected:active,
QTableView#BatchCompareTable::item:selected:active,
QTableWidget#BatchCompareTable::item:selected:!active,
QTableView#BatchCompareTable::item:selected:!active {{
    background-color: {t.table_selected};
    color: {t.text_primary};
}}
QTableWidget#MarketTable::item:alternate:selected,
QTableView#MarketTable::item:alternate:selected,
QTableWidget#MarketTable::item:alternate:selected:active,
QTableView#MarketTable::item:alternate:selected:active,
QTableWidget#MarketTable::item:alternate:selected:!active,
QTableView#MarketTable::item:alternate:selected:!active,
QTableWidget#ScreenerResultsTable::item:alternate:selected,
QTableView#ScreenerResultsTable::item:alternate:selected,
QTableWidget#ScreenerResultsTable::item:alternate:selected:active,
QTableView#ScreenerResultsTable::item:alternate:selected:active,
QTableWidget#ScreenerResultsTable::item:alternate:selected:!active,
QTableView#ScreenerResultsTable::item:alternate:selected:!active,
QTableWidget#BatchCompareTable::item:alternate:selected,
QTableView#BatchCompareTable::item:alternate:selected,
QTableWidget#BatchCompareTable::item:alternate:selected:active,
QTableView#BatchCompareTable::item:alternate:selected:active,
QTableWidget#BatchCompareTable::item:alternate:selected:!active,
QTableView#BatchCompareTable::item:alternate:selected:!active {{
    background-color: {t.table_selected};
    color: {t.text_primary};
}}
QTableWidget#MarketTable::item:hover,
QTableView#MarketTable::item:hover,
QTableWidget#ScreenerResultsTable::item:hover,
QTableView#ScreenerResultsTable::item:hover,
QTableWidget#BatchCompareTable::item:hover,
QTableView#BatchCompareTable::item:hover {{
    background-color: {t.table_hover};
}}
QTableWidget#MarketTable::item:alternate,
QTableView#MarketTable::item:alternate,
QTableWidget#ScreenerResultsTable::item:alternate,
QTableView#ScreenerResultsTable::item:alternate,
QTableWidget#BatchCompareTable::item:alternate,
QTableView#BatchCompareTable::item:alternate {{
    background-color: {t.table_alt};
}}
QPushButton#PrimaryRunButton {{
    background-color: {t.action_btn_bg};
    border: 1px solid {t.action_btn_border};
    border-radius: 4px;
    padding: 6px 18px;
    color: {t.action_btn_text};
    font-weight: bold;
    font-size: 13px;
}}
QPushButton#PrimaryRunButton:hover {{
    background-color: {t.action_btn_hover_bg};
    border-color: {t.action_btn_hover_border};
}}
QPushButton#PrimaryRunButton:pressed {{
    background-color: {t.action_btn_pressed_bg};
}}
QPushButton#PrimaryRunButton:disabled {{
    background-color: {t.action_btn_disabled_bg};
    border-color: {t.action_btn_disabled_border};
    color: {t.action_btn_disabled_text};
}}
QLineEdit#PageJumpInput {{
    background-color: {t.input_bg};
    border: 1px solid {t.input_border};
    border-radius: 3px;
    padding: 2px 6px;
    color: {t.input_text};
    font-size: 12px;
    max-width: 48px;
}}
QLineEdit#PageJumpInput:focus {{
    border-color: {t.accent};
}}
QComboBox#BoardCombo {{
    background-color: {t.combo_bg};
    border: 1px solid {t.combo_border};
    border-radius: 4px;
    color: {t.combo_text};
    padding: 4px 10px;
    padding-right: 26px;
    font-size: 13px;
    min-width: 90px;
}}
QComboBox#BoardCombo:hover {{
    border-color: {t.combo_hover_border};
    background-color: {t.combo_hover_bg};
}}
QComboBox#BoardCombo:focus {{
    border-color: {t.accent};
}}
QComboBox#BoardCombo:disabled {{
    color: {t.combo_disabled_text};
    background-color: {t.combo_disabled_bg};
}}
QComboBox#BoardCombo::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: center right;
    width: 22px;
    border: none;
}}
QComboBox#BoardCombo QAbstractItemView {{
    background-color: {t.combo_popup_bg};
    color: {t.combo_text};
    border: 1px solid {t.combo_popup_border};
    selection-background-color: {t.combo_selection_bg};
    selection-color: {t.action_btn_text};
    outline: none;
    padding: 4px 0;
}}
QComboBox#BoardCombo QAbstractItemView::item {{
    min-height: 28px;
    padding: 4px 12px;
    color: {t.combo_text};
}}
QComboBox#BoardCombo QAbstractItemView::item:hover {{
    background-color: {t.combo_item_hover_bg};
    color: {t.text_primary};
}}
QComboBox#BoardCombo QAbstractItemView::item:selected {{
    background-color: {t.combo_selection_bg};
    color: {t.action_btn_text};
}}
QTabBar#ScreenerRunFilterTabs {{
    background-color: transparent;
}}
QTabBar#ScreenerRunFilterTabs::tab {{
    background-color: {t.tab_bg};
    color: {t.tab_text};
    border: 1px solid {t.tab_border};
    border-bottom: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    padding: 5px 12px;
    margin-right: 2px;
    font-size: 11px;
}}
QTabBar#ScreenerRunFilterTabs::tab:selected {{
    background-color: {t.tab_selected_bg};
    color: {t.tab_selected_text};
    border-color: {t.tab_selected_border};
}}
QTabBar#ScreenerRunFilterTabs::tab:hover {{
    color: {t.tab_hover_text};
}}
QLabel#ScreenerUnreadBadge {{
    background-color: {t.accent};
    color: {t.action_btn_text};
    border-radius: 8px;
    font-size: 10px;
    font-weight: bold;
    min-width: 16px;
    max-width: 24px;
    min-height: 16px;
    padding: 0 4px;
}}
QListWidget#AiSessionListWidget::item {{
    padding: 0;
    border-radius: 6px;
    margin: 2px 0;
}}
QListWidget#AiSessionListWidget::item:selected,
QListWidget#AiSessionListWidget::item:hover {{
    background-color: transparent;
}}
QFrame#ScreenerRunRow {{
    background-color: transparent;
    border-radius: 6px;
    border-left: 3px solid transparent;
}}
QFrame#ScreenerRunRow[diffHighlight="true"] {{
    border-left: 3px solid {t.run_row_unread};
}}
QFrame#ScreenerRunRow[active="true"] {{
    background-color: {t.run_row_active_bg};
    border-left: 3px solid {t.accent};
}}
QFrame#ScreenerRunRow:hover {{
    background-color: {t.run_row_hover_bg};
}}
QLabel#ScreenerRunRowTitle {{
    color: {t.run_row_title};
    font-size: 12px;
    min-height: 16px;
}}
QLabel#ScreenerRunRowSubtitle {{
    color: {t.run_row_subtitle};
    font-size: 10px;
    min-height: 14px;
}}
QCheckBox#ScreenerRunCheck {{
    spacing: 0;
}}
QCheckBox#ScreenerRunCheck::indicator {{
    width: 14px;
    height: 14px;
    border: 1px solid {t.checkbox_border};
    border-radius: 3px;
    background-color: {t.checkbox_bg};
}}
QCheckBox#ScreenerRunCheck::indicator:checked {{
    background-color: {t.accent};
    border-color: {t.accent};
}}
"""
