"""由 ThemeTokens 生成页面/对话框附加 QSS。"""

from __future__ import annotations

import html
from collections.abc import Sequence
from typing import Protocol

from vnpy_common.ui.theme.tokens import ThemeTokens


class SchedulerRunLogRecord(Protocol):
    """调度任务执行记录（与 vnpy_ashare.scheduler.manager.JobRunRecord 字段对齐）。"""

    running: bool
    skipped: bool
    success: bool
    message: str
    finished_at: str
    started_at: str | None
    job_name: str
    detail_lines: list[str]


def build_settings_stylesheet(t: ThemeTokens) -> str:
    return f"""
QDialog#SettingsDialog {{
    background-color: {t.app_bg};
    color: {t.text_primary};
}}
QScrollArea#SettingsScroll,
QWidget#SettingsScrollBody {{
    background-color: transparent;
    border: none;
}}
QLabel#SettingsHint {{
    color: {t.text_secondary};
    font-size: 12px;
    padding: 8px 10px;
    background-color: {t.panel_bg};
    border: 1px solid {t.panel_border};
    border-radius: 6px;
}}
QLabel#SettingsMeta {{
    color: {t.text_secondary};
    font-size: 12px;
    margin-bottom: 4px;
}}
QLabel#SettingsSubheading {{
    color: {t.text_section};
    font-size: 12px;
    font-weight: bold;
    margin-top: 4px;
}}
QPushButton#SettingsSegmentLeft,
QPushButton#SettingsSegmentRight {{
    background-color: {t.input_bg};
    border: 1px solid {t.input_border};
    padding: 6px 20px;
    color: {t.text_secondary};
    font-size: 12px;
    min-width: 88px;
}}
QPushButton#SettingsSegmentLeft {{
    border-top-left-radius: 4px;
    border-bottom-left-radius: 4px;
    border-top-right-radius: 0;
    border-bottom-right-radius: 0;
    border-right: none;
}}
QPushButton#SettingsSegmentRight {{
    border-top-right-radius: 4px;
    border-bottom-right-radius: 4px;
    border-top-left-radius: 0;
    border-bottom-left-radius: 0;
}}
QPushButton#SettingsSegmentLeft:checked,
QPushButton#SettingsSegmentRight:checked {{
    background-color: {t.action_btn_bg};
    border-color: {t.action_btn_border};
    color: {t.action_btn_text};
    font-weight: bold;
}}
QPushButton#SettingsSegmentLeft:hover:!checked,
QPushButton#SettingsSegmentRight:hover:!checked {{
    background-color: {t.btn_hover_bg};
    color: {t.text_primary};
}}
QGroupBox#SettingsGroup {{
    background-color: {t.panel_bg};
    border: 1px solid {t.panel_border};
    border-radius: 6px;
    margin-top: 12px;
    padding: 16px 12px 12px 12px;
    font-size: 12px;
    color: {t.text_secondary};
}}
QDialog#SettingsDialog QGroupBox#SettingsGroup {{
    min-height: 48px;
}}
QGroupBox#SettingsGroup::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 6px;
    left: 10px;
    color: {t.text_section};
    font-weight: bold;
}}
QTableWidget#SettingsEnvTable {{
    background-color: {t.table_bg};
    gridline-color: {t.table_grid};
    border: 1px solid {t.table_grid};
    border-radius: 4px;
    font-size: 12px;
    alternate-background-color: {t.table_alt};
    selection-background-color: {t.table_selected};
    selection-color: {t.text_primary};
}}
QTableWidget#SettingsEnvTable::item {{
    padding-left: 10px;
    padding-right: 10px;
    border: none;
}}
QTableWidget#SettingsEnvTable::item:alternate {{
    background-color: {t.table_alt};
}}
QTableWidget#SettingsEnvTable::item:selected {{
    background-color: {t.table_selected};
    color: {t.text_primary};
}}
QTableWidget#SettingsEnvTable QHeaderView::section {{
    background-color: {t.header_bg};
    color: {t.header_text};
    padding-left: 10px;
    padding-right: 10px;
    border: none;
    border-bottom: 1px solid {t.header_border};
    border-right: 1px solid {t.header_border};
    font-size: 12px;
    min-height: 34px;
}}
QLabel#SettingsFormLabel {{
    color: {t.text_secondary};
    font-size: 12px;
    min-width: 140px;
}}
QSpinBox#SettingsInput {{
    background-color: {t.input_bg};
    border: 1px solid {t.input_border};
    border-radius: 4px;
    padding: 4px 8px;
    color: {t.input_text};
    min-height: 28px;
    font-size: 13px;
}}
QSpinBox#SettingsInput::up-button,
QSpinBox#SettingsInput::down-button {{
    width: 16px;
    background-color: {t.btn_bg};
    border: none;
}}
QLineEdit#SettingsInput,
QComboBox#SettingsInput {{
    background-color: {t.input_bg};
    border: 1px solid {t.input_border};
    border-radius: 4px;
    padding: 6px 10px;
    color: {t.input_text};
    min-height: 28px;
    font-size: 13px;
}}
QLineEdit#SettingsInput:focus,
QComboBox#SettingsInput:focus {{
    border-color: {t.accent};
}}
QLineEdit#SettingsInput:read-only {{
    color: {t.input_disabled_text};
    background-color: {t.input_disabled_bg};
    border-color: {t.panel_border};
}}
QSpinBox#SettingsInput:focus {{
    border-color: {t.accent};
}}
QComboBox#SettingsInput::drop-down {{
    border: none;
    width: 22px;
}}
QComboBox#SettingsInput QAbstractItemView {{
    background-color: {t.combo_popup_bg};
    color: {t.combo_text};
    border: 1px solid {t.combo_popup_border};
    selection-background-color: {t.combo_selection_bg};
}}
QCheckBox#SettingsCheck {{
    color: {t.text_primary};
    spacing: 8px;
}}
QPushButton#SettingsPrimaryButton {{
    background-color: {t.action_btn_bg};
    border: 1px solid {t.action_btn_border};
    border-radius: 4px;
    padding: 6px 18px;
    color: {t.action_btn_text};
    font-weight: bold;
}}
QPushButton#SettingsPrimaryButton:hover {{
    background-color: {t.action_btn_hover_bg};
}}
QPushButton#SettingsSecondaryButton {{
    background-color: {t.secondary_btn_bg};
    border: 1px solid {t.secondary_btn_border};
    border-radius: 4px;
    padding: 6px 16px;
    color: {t.secondary_btn_text};
}}
QPushButton#SettingsSecondaryButton:hover {{
    background-color: {t.secondary_btn_hover_bg};
    color: {t.text_primary};
}}
QTabWidget#SettingsTabs::pane {{
    border: 1px solid {t.panel_border};
    border-radius: 6px;
    background-color: transparent;
    top: -1px;
    padding: 4px;
}}
QTabWidget#SettingsTabs > QTabBar::tab {{
    background-color: {t.input_bg};
    border: 1px solid {t.input_border};
    border-bottom: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    padding: 8px 18px;
    margin-right: 4px;
    color: {t.text_secondary};
    font-size: 12px;
}}
QTabWidget#SettingsTabs > QTabBar::tab:selected {{
    background-color: {t.panel_bg};
    color: {t.text_primary};
    font-weight: bold;
}}
QTabWidget#SettingsTabs > QTabBar::tab:hover:!selected {{
    background-color: {t.btn_hover_bg};
    color: {t.text_primary};
}}
"""


def build_scheduler_table_stylesheet(t: ThemeTokens) -> str:
    return f"""
QTableWidget#SchedulerTable {{
    background-color: {t.table_bg};
    gridline-color: {t.table_grid};
    border: 1px solid {t.table_grid};
    border-radius: 4px;
    font-size: 12px;
}}
QTableWidget#SchedulerTable::item {{
    padding: 6px 8px;
}}
QTableWidget#SchedulerTable QPushButton#ActionButton,
QTableWidget#SchedulerTable QPushButton#SecondaryButton {{
    padding: 4px 10px;
    font-size: 12px;
}}
QTableWidget#SchedulerTable QHeaderView::section {{
    background-color: {t.header_bg};
    color: {t.header_text};
    padding: 8px 10px;
    border: none;
    border-right: 1px solid {t.header_border};
    font-size: 12px;
}}
"""


def build_scheduler_page_stylesheet(t: ThemeTokens) -> str:
    return f"""
QLabel#SchedulerPageTitle {{
    color: {t.text_primary};
    font-size: 16px;
    font-weight: 600;
}}
QLabel#SchedulerHint {{
    color: {t.text_muted};
    font-size: 12px;
}}
QLabel#SchedulerSectionLabel {{
    color: {t.text_section};
    font-size: 12px;
    font-weight: 600;
}}
QWidget#SchedulerPanel {{
    background-color: {t.panel_bg};
    border: 1px solid {t.panel_border};
    border-radius: 6px;
}}
QTextEdit#SchedulerLogView {{
    background-color: {t.screener_log_bg};
    border: none;
    color: {t.screener_log_text};
    font-family: Menlo, Monaco, "Courier New", monospace;
    font-size: 12px;
    padding: 10px 12px;
}}
"""


def build_vnpy_page_stylesheet(t: ThemeTokens) -> str:
    return f"""
QWidget#BacktestPage,
QWidget#DataManagerPage {{
    background-color: {t.app_bg};
    color: {t.text_primary};
}}
QWidget#BacktestPage QLabel,
QWidget#DataManagerPage QLabel {{
    color: {t.text_secondary};
    font-size: 12px;
}}
QWidget#BacktestPage QLineEdit#BacktestInput,
QWidget#BacktestPage QDateEdit#BacktestInput,
QWidget#DataManagerPage QLineEdit {{
    background-color: {t.input_bg};
    border: 1px solid {t.input_border};
    border-radius: 4px;
    padding: 4px 8px;
    color: {t.input_text};
    min-height: 26px;
    font-size: 13px;
}}
QWidget#BacktestPage QLineEdit#BacktestInput:focus,
QWidget#BacktestPage QDateEdit#BacktestInput:focus {{
    border-color: {t.accent};
}}
QWidget#BacktestPage QDateEdit#BacktestInput::drop-down,
QWidget#BacktestPage QDateEdit#BacktestInput::down-arrow {{
    border: none;
}}
QTextEdit#BacktestLogView {{
    background-color: {t.screener_log_bg};
    border: 1px solid {t.table_grid};
    border-radius: 4px;
    color: {t.screener_log_text};
    font-family: Menlo, Monaco, "Courier New", monospace;
    font-size: 12px;
}}
QTableWidget#BacktestStatisticsTable,
QTreeWidget#DataManagerTree,
QTableWidget#DataManagerTable {{
    background-color: {t.table_bg};
    gridline-color: {t.table_grid};
    border: 1px solid {t.table_grid};
    border-radius: 4px;
    font-size: 12px;
    color: {t.text_primary};
    alternate-background-color: {t.table_alt};
}}
QTableWidget#BacktestStatisticsTable::item,
QTreeWidget#DataManagerTree::item,
QTableWidget#DataManagerTable::item {{
    padding: 4px 6px;
}}
QHeaderView::section {{
    background-color: {t.header_bg};
    color: {t.header_text};
    padding: 6px 8px;
    border: none;
    border-right: 1px solid {t.header_border};
    font-size: 12px;
}}
QWidget#BatchCompareSummaryBar {{
    background-color: {t.panel_bg};
    border: 1px solid {t.panel_border};
    border-radius: 6px;
}}
QWidget#BatchCompareSessionPanel,
QWidget#BatchCompareResultPanel {{
    background-color: {t.panel_bg};
    border: 1px solid {t.panel_border};
    border-radius: 6px;
}}
QListWidget#BatchSessionListWidget {{
    background-color: transparent;
    border: none;
    border-radius: 0;
    outline: none;
    color: {t.run_row_title};
    font-size: 12px;
}}
QListWidget#BatchSessionListWidget::item {{
    padding: 10px 12px;
    border-bottom: 1px solid {t.table_grid};
}}
QListWidget#BatchSessionListWidget::item:selected {{
    background-color: {t.table_selected};
    color: {t.text_primary};
}}
QListWidget#BatchSessionListWidget::item:hover {{
    background-color: {t.table_hover};
}}
QGroupBox#BacktestFormBox {{
    background-color: {t.panel_bg};
    border: 1px solid {t.panel_border};
    border-radius: 6px;
    margin-top: 4px;
    padding: 14px 12px 12px 12px;
    font-size: 12px;
    color: {t.text_secondary};
}}
QGroupBox#BacktestFormBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 6px;
    left: 10px;
    color: {t.text_section};
    font-weight: bold;
}}
QWidget#BacktestChartFrame {{
    background-color: {t.depth_bg};
    border: 1px solid {t.table_grid};
    border-radius: 4px;
}}
QFormLayout QLabel {{
    color: {t.text_secondary};
    font-size: 12px;
}}
"""


def format_scheduler_run_log_html(t: ThemeTokens, records: Sequence[SchedulerRunLogRecord]) -> str:
    if not records:
        return f'<p style="color:{t.text_muted};margin:0;">暂无执行记录。</p>'

    lines: list[str] = []
    for record in records:
        if record.running:
            mark = "运行中"
            mark_color = t.accent
        elif record.skipped:
            mark = "跳过"
            mark_color = t.text_muted
        else:
            mark = "成功" if record.success else "失败"
            mark_color = t.semantic_success if record.success else t.semantic_error
        message = html.escape(record.message)
        time_text = html.escape(record.finished_at or record.started_at or "")
        lines.append(
            "<p style='margin:0 0 4px 0;line-height:1.5;'>"
            f"<span style='color:{t.text_muted};'>{time_text}</span> "
            f"<span style='color:{t.text_primary};'>{html.escape(record.job_name)}</span> "
            f"<span style='color:{mark_color};'>{mark}</span> "
            f"<span style='color:{t.text_secondary};'>{message}</span>"
            "</p>"
        )
        detail_lines = getattr(record, "detail_lines", None) or []
        if detail_lines:
            visible = detail_lines[-120:]
            omitted = len(detail_lines) - len(visible)
            detail_body = "<br/>".join(html.escape(line) for line in visible)
            if omitted > 0:
                detail_body = f"<span style='color:{t.text_muted};'>… 省略较早 {omitted} 行</span><br/>" + detail_body
            lines.append(
                "<div style='margin:0 0 10px 12px;padding:6px 8px;"
                f"background:{t.depth_bg};border:1px solid {t.table_grid};border-radius:4px;"
                "font-family:Menlo,Consolas,monospace;font-size:11px;line-height:1.45;"
                f"color:{t.text_secondary};white-space:normal;'>{detail_body}</div>"
            )
    return "".join(lines)


def format_scheduler_empty_html(t: ThemeTokens, message: str) -> str:
    return f'<p style="color:{t.text_muted};margin:0;">{html.escape(message)}</p>'


def build_market_overview_stylesheet(t: ThemeTokens) -> str:
    return build_market_page_stylesheet(t)


def build_market_discovery_stylesheet(t: ThemeTokens) -> str:
    return ""


def build_market_page_stylesheet(t: ThemeTokens) -> str:
    return f"""
QWidget#MarketHeaderPanel {{
    background-color: {t.index_ticker_bg};
    border-bottom: 1px solid {t.panel_border};
}}
QFrame#MarketHeaderDivider {{
    background-color: {t.panel_border};
    border: none;
    max-height: 1px;
}}
QWidget#MarketOverviewPanel {{
    background-color: transparent;
}}
QWidget#MarketStatsBar {{
    background-color: transparent;
}}
QFrame#MarketStatChip {{
    background-color: {t.panel_bg};
    border: 1px solid {t.panel_border};
    border-radius: 8px;
    min-width: 56px;
}}
QLabel#MarketStatChipLabel {{
    color: {t.text_muted};
    font-size: 10px;
}}
QLabel#MarketStatChipValue {{
    color: {t.text_primary};
    font-size: 14px;
    font-weight: 600;
}}
QFrame#MarketStatDivider {{
    color: {t.panel_border};
    background-color: {t.panel_border};
    margin: 6px 2px;
    max-width: 1px;
}}
QWidget#MarketBreadthRatioBar {{
    background-color: {t.input_bg};
    border-radius: 2px;
}}
QWidget#MarketFearGauge {{
    background-color: {t.panel_bg};
    border: 1px solid {t.panel_border};
    border-radius: 8px;
    min-width: 132px;
}}
QProgressBar#MarketFearGaugeBar {{
    background-color: {t.input_bg};
    border: none;
    border-radius: 2px;
}}
QProgressBar#MarketFearGaugeBar::chunk {{
    background-color: {t.accent};
    border-radius: 2px;
}}
QLabel#MarketStatsUpdated {{
    color: {t.text_muted};
    font-size: 11px;
    padding-left: 8px;
}}
QWidget#MarketOverviewToolbar {{
    background-color: transparent;
}}
QScrollArea#IndexCardScroll,
QScrollArea#SectorCardScroll {{
    background-color: transparent;
    border: none;
}}
QWidget#IndexCardHost,
QWidget#SectorCardHost {{
    background-color: transparent;
}}
QFrame#IndexCard {{
    background-color: {t.panel_bg};
    border: 1px solid {t.panel_border};
    border-radius: 8px;
    min-width: 100px;
}}
QFrame#IndexCard:hover {{
    border-color: {t.accent};
}}
QLabel#IndexCardName {{
    color: {t.text_secondary};
    font-size: 11px;
}}
QLabel#IndexCardPrice {{
    color: {t.text_primary};
    font-size: 14px;
    font-weight: 600;
}}
QLabel#IndexCardPct {{
    font-size: 12px;
    font-weight: 600;
}}
QPushButton#OverviewTabButton {{
    background-color: transparent;
    border: 1px solid {t.panel_border};
    border-radius: 6px;
    padding: 3px 14px;
    color: {t.text_secondary};
    font-size: 11px;
    min-width: 48px;
}}
QPushButton#OverviewTabButton:hover {{
    border-color: {t.accent};
    color: {t.text_primary};
}}
QPushButton#OverviewTabButton:checked {{
    background-color: {t.panel_bg};
    color: {t.text_primary};
    border-color: {t.accent};
    font-weight: 600;
}}
QFrame#SectorCard {{
    background-color: {t.panel_bg};
    border: 1px solid {t.panel_border};
    border-radius: 8px;
    min-width: 88px;
}}
QFrame#SectorCard:hover {{
    border-color: {t.accent};
}}
QLabel#SectorCardName {{
    color: {t.text_secondary};
    font-size: 11px;
}}
QLabel#SectorCardPct {{
    font-size: 13px;
    font-weight: 600;
}}
QLabel#SectorCardCount {{
    color: {t.text_muted};
    font-size: 10px;
}}
QLabel#SectorCardEmpty {{
    color: {t.text_muted};
    font-size: 12px;
    padding: 8px 12px;
}}
QLabel#MarketIndustryChip {{
    background-color: {t.panel_bg};
    border: 1px solid {t.accent};
    border-radius: 6px;
    padding: 3px 10px;
    color: {t.text_primary};
    font-size: 11px;
    font-weight: 600;
}}
QToolButton#MarketIndustryClear {{
    background-color: transparent;
    border: 1px solid {t.panel_border};
    border-radius: 6px;
    padding: 2px 6px;
    color: {t.text_muted};
    font-size: 12px;
    font-weight: 700;
}}
QToolButton#MarketIndustryClear:hover {{
    border-color: {t.accent};
    color: {t.text_primary};
}}
QComboBox#MarketIndustryCombo {{
    background-color: {t.panel_bg};
    border: 1px solid {t.panel_border};
    border-radius: 6px;
    color: {t.text_primary};
    padding: 3px 8px;
    padding-right: 22px;
    font-size: 11px;
    min-width: 120px;
}}
QComboBox#MarketIndustryCombo:hover {{
    border-color: {t.accent};
}}
QComboBox#MarketIndustryCombo:focus {{
    border-color: {t.accent};
}}
QComboBox#MarketIndustryCombo::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: center right;
    width: 18px;
    border: none;
}}
QComboBox#MarketIndustryCombo QAbstractItemView {{
    background-color: {t.combo_popup_bg};
    color: {t.combo_text};
    border: 1px solid {t.combo_popup_border};
    selection-background-color: {t.combo_selection_bg};
    selection-color: {t.action_btn_text};
    outline: none;
    padding: 4px 0;
}}
QWidget#MarketDiscoveryStrip {{
    background-color: transparent;
}}
QLabel#MarketDiscoverySectionTitle {{
    color: {t.text_primary};
    font-size: 12px;
    font-weight: 600;
}}
QLabel#MarketDiscoveryTitle {{
    color: {t.text_muted};
    font-size: 11px;
    font-weight: 600;
    min-width: 28px;
}}
QLabel#MarketDiscoveryEmpty {{
    color: {t.text_muted};
    font-size: 11px;
}}
QFrame#MarketDiscoveryDivider {{
    background-color: {t.panel_border};
    border: none;
    margin: 2px 4px;
}}
QScrollArea#MarketDiscoveryScroll {{
    background-color: transparent;
    border: none;
}}
QPushButton#MarketDiscoveryChip {{
    background-color: {t.panel_bg};
    border: 1px solid {t.panel_border};
    border-radius: 6px;
    padding: 4px 10px;
    font-size: 11px;
    color: {t.text_primary};
}}
QPushButton#MarketDiscoveryChip:hover {{
    border-color: {t.accent};
}}
QPushButton#MarketDiscoveryChip[chipTone="rise"] {{
    color: {t.market_rise};
    border-color: {t.market_rise};
}}
QPushButton#MarketDiscoveryChip[chipTone="fall"] {{
    color: {t.market_fall};
    border-color: {t.market_fall};
}}
QPushButton#MarketDiscoveryChip[chipTone="flat"] {{
    color: {t.text_secondary};
}}
QWidget#MarketRankSidebar {{
    background-color: {t.panel_bg};
    border-right: none;
}}
QWidget#MarketRankSidebarBody {{
    background-color: transparent;
}}
QWidget#MarketRankSidebarHandle {{
    background-color: {t.panel_bg};
    border-left: 1px solid {t.panel_border};
}}
QToolButton#MarketRankSidebarCollapseButton {{
    background-color: transparent;
    border: 1px solid {t.panel_border};
    border-radius: 4px;
    padding: 0;
}}
QToolButton#MarketRankSidebarCollapseButton:hover {{
    border-color: {t.accent};
    background-color: {t.nav_hover_bg};
}}
QLabel#MarketRankSidebarTitle {{
    color: {t.text_muted};
    font-size: 11px;
    font-weight: 600;
    padding: 10px 12px 4px 12px;
}}
QListWidget#RankSidebar {{
    background-color: transparent;
    border: none;
    outline: none;
    padding: 0 4px 8px 4px;
    font-size: 12px;
}}
QListWidget#RankSidebar::item {{
    color: {t.text_primary};
    padding: 6px 8px;
    border-radius: 6px;
    margin: 1px 0;
}}
QListWidget#RankSidebar::item:hover {{
    background-color: {t.nav_hover_bg};
}}
QListWidget#RankSidebar::item:selected {{
    background-color: {t.nav_selected_bg};
    color: {t.accent};
    font-weight: 600;
}}
QWidget#MarketToolbar {{
    background-color: {t.panel_bg};
    border-bottom: 1px solid {t.panel_border};
}}
QWidget#MarketContent {{
    background-color: {t.app_bg};
}}
QSplitter#MarketRankSplitter::handle {{
    background-color: {t.panel_border};
    width: 1px;
}}
"""


def build_radar_stylesheet(t: ThemeTokens) -> str:
    return f"""
QToolButton#RadarSectionToggle {{
    color: {t.text_muted};
    border: none;
    padding: 0 4px;
    font-size: 12px;
}}
QToolButton#RadarSectionToggle:hover {{
    color: {t.accent};
}}
QTabWidget#RadarBoardTabs::pane {{
    border: none;
    background: transparent;
    top: 0;
}}
QTabWidget#RadarBoardTabs > QTabBar {{
    border: none;
    background: transparent;
    qproperty-drawBase: 0;
}}
QTabWidget#RadarBoardTabs > QTabBar::tab {{
    background: transparent;
    color: {t.text_muted};
    padding: 6px 14px;
    margin-right: 6px;
    border: none;
    border-bottom: 2px solid transparent;
    font-size: 13px;
    font-weight: 600;
}}
QTabWidget#RadarBoardTabs > QTabBar::tab:selected {{
    color: {t.accent};
    border-bottom: 2px solid {t.accent};
}}
QTabWidget#RadarResonanceTabs::pane {{
    border: none;
    background: transparent;
}}
QTabWidget#RadarResonanceTabs > QTabBar::tab {{
    color: {t.text_muted};
    padding: 4px 10px;
    margin-right: 4px;
    border-bottom: 2px solid transparent;
}}
QTabWidget#RadarResonanceTabs > QTabBar::tab:selected {{
    color: {t.accent};
    border-bottom: 2px solid {t.accent};
}}
QScrollArea#RadarBoardScroll {{
    background: transparent;
    border: none;
}}
QWidget#RadarBoardContent {{
    background: transparent;
}}
QFrame#RadarSectionDivider {{
    color: {t.panel_border};
    background-color: {t.panel_border};
    max-height: 1px;
    margin: 4px 8px;
}}
QLabel#RadarSectionTitle {{
    color: {t.text_primary};
    font-size: 14px;
    font-weight: 700;
}}
QLabel#RadarSectionHint {{
    color: {t.text_muted};
    font-size: 11px;
}}
QLabel#RadarSectionModeBadgeStatistical {{
    color: {t.text_secondary};
    font-size: 10px;
    padding: 1px 8px;
    border: 1px solid {t.panel_border};
    border-radius: 4px;
}}
QLabel#RadarSectionModeBadgePredictive {{
    color: {t.accent};
    font-size: 10px;
    padding: 1px 8px;
    border: 1px solid {t.accent};
    border-radius: 4px;
    background-color: rgba(128, 128, 128, 0.08);
}}
QFrame#RadarCardLive {{
    background-color: {t.panel_bg};
    border: 1px solid {t.panel_border};
    border-radius: 8px;
}}
QFrame#RadarCardManual {{
    background-color: {t.panel_bg};
    border: 1px dashed {t.panel_border};
    border-radius: 8px;
}}
QFrame#RadarCardPredictive {{
    background-color: {t.panel_bg};
    border: 1px dashed {t.accent};
    border-radius: 8px;
}}
QLabel#RadarCardKindBadgeStatistical,
QLabel#RadarCardKindBadgePredictive,
QLabel#RadarCardModeBadge,
QLabel#RadarCardModeBadgeOff,
QLabel#RadarCardModeBadgeLive {{
    font-size: 10px;
    padding: 2px 7px;
    border-radius: 4px;
    border: 1px solid {t.panel_border};
}}
QLabel#RadarCardKindBadgeStatistical,
QLabel#RadarCardModeBadge,
QLabel#RadarCardModeBadgeOff {{
    color: {t.text_muted};
}}
QLabel#RadarCardKindBadgePredictive {{
    color: {t.accent};
    border-color: {t.accent};
}}
QLabel#RadarCardModeBadgeLive {{
    color: {t.accent};
    border-color: {t.accent};
}}
QWidget#RadarCardBadgeGroup {{
    background: transparent;
}}
QWidget#RadarCardHeaderDivider {{
    background-color: {t.panel_border};
}}
QWidget#RadarCardHeaderActions {{
    background: transparent;
}}
QScrollArea#RadarCardScroll {{
    background: transparent;
    border: none;
}}
QStackedWidget#RadarCardBodyStack,
QWidget#RadarCardEmptyPage {{
    background: transparent;
}}
QWidget#RadarCardRowsHost {{
    background: transparent;
}}
QFrame#RadarStockRow {{
    background-color: {t.index_ticker_bg};
    border: 1px solid {t.panel_border};
    border-radius: 6px;
}}
QFrame#RadarStockRow:hover {{
    border-color: {t.accent};
}}
QLabel#RadarResonanceBadge {{
    color: {t.accent};
    font-size: 12px;
    font-weight: 700;
    min-width: 12px;
}}
QLabel#RadarRowName {{
    color: {t.text_primary};
    font-size: 13px;
    font-weight: 600;
}}
QLabel#RadarRowSymbol {{
    color: {t.text_muted};
    font-size: 11px;
}}
QLabel#RadarRowPrice {{
    color: {t.text_primary};
    font-size: 13px;
    font-weight: 600;
}}
QLabel#RadarMetricChip {{
    color: {t.text_secondary};
    font-size: 11px;
    background-color: transparent;
    border: none;
    padding: 0;
}}
QLabel#RadarSubChip {{
    color: {t.text_muted};
    font-size: 10px;
}}
QLabel#RadarChangeChip {{
    font-size: 11px;
}}
QLabel#RadarCardTitle {{
    color: {t.text_primary};
    font-size: 13px;
    font-weight: 600;
}}
QLabel#RadarCardSubtitle {{
    color: {t.text_muted};
    font-size: 11px;
    min-height: 15px;
}}
QLabel#RadarCardEmpty {{
    color: {t.text_muted};
    font-size: 12px;
    padding: 24px 12px;
}}
QLabel#RadarCardMeta {{
    color: {t.text_muted};
    font-size: 11px;
}}
QPushButton#RadarCardAi,
QPushButton#RadarCardViewRun,
QPushButton#RadarCardAddAll,
QPushButton#RadarCardSectorFlow,
QPushButton#RadarCardTrainModel {{
    color: {t.text_secondary};
    background-color: transparent;
    border: none;
    font-size: 11px;
    padding: 2px 6px;
}}
QPushButton#RadarCardAi:hover,
QPushButton#RadarCardViewRun:hover,
QPushButton#RadarCardAddAll:hover,
QPushButton#RadarCardSectorFlow:hover,
QPushButton#RadarCardTrainModel:hover {{
    color: {t.accent};
}}
QPushButton#RadarCardViewRun {{
    color: {t.accent};
}}
QPushButton#RadarCardAddAll {{
    color: {t.accent};
}}
QListWidget#RadarCardList {{
    background: transparent;
    border: none;
    color: {t.text_primary};
    font-size: 12px;
}}
QListWidget#RadarCardList::item {{
    padding: 6px 2px;
    border-bottom: 1px solid {t.panel_border};
}}
QListWidget#RadarCardList::item:selected {{
    background-color: {t.menu_selected_bg};
}}
QComboBox#RadarCardVariant {{
    min-width: 72px;
    max-width: 108px;
    max-height: 24px;
    font-size: 11px;
}}
QComboBox#RadarCardRefreshInterval,
QComboBox#RadarCardFullRefreshInterval {{
    min-width: 72px;
    max-height: 24px;
    font-size: 11px;
}}
QWidget#RadarCardRefreshGroup {{
    background: transparent;
}}
QToolButton#RadarCardRefresh,
QToolButton#RadarCardRefreshMenu {{
    color: {t.text_muted};
    background-color: transparent;
    border: 1px solid {t.panel_border};
    border-radius: 4px;
    font-size: 13px;
    min-width: 24px;
    min-height: 24px;
    padding: 0 5px;
}}
QToolButton#RadarCardRefreshMenu {{
    font-size: 10px;
    min-width: 20px;
    padding: 0 4px;
}}
QToolButton#RadarCardRefresh:hover,
QToolButton#RadarCardRefreshMenu:hover {{
    color: {t.accent};
    border-color: {t.accent};
}}
QToolButton#RadarCardRefresh:disabled,
QToolButton#RadarCardRefreshMenu:disabled {{
    color: {t.text_muted};
    border-color: {t.panel_border};
}}
QFrame#RadarResonancePanel {{
    background-color: {t.panel_bg};
    border: none;
}}
QWidget#RadarResonanceSection {{
    background-color: {t.panel_bg};
    border-left: 1px solid {t.panel_border};
}}
QWidget#RadarResonanceHandle {{
    background-color: {t.panel_bg};
}}
QToolButton#RadarResonanceCollapseButton {{
    color: {t.text_muted};
    border: 1px solid {t.panel_border};
    border-radius: 4px;
    background-color: {t.index_ticker_bg};
    padding: 0;
}}
QToolButton#RadarResonanceCollapseButton:hover {{
    color: {t.text_primary};
    border-color: {t.accent};
}}
QToolButton#RadarResonanceCollapseButton:checked {{
    color: {t.accent};
    border-color: {t.accent};
}}
QLabel#RadarResonanceTitle {{
    color: {t.text_primary};
    font-size: 14px;
    font-weight: 700;
}}
QLabel#RadarResonanceHint {{
    color: {t.text_muted};
    font-size: 11px;
}}
QLabel#RadarResonanceCount {{
    color: {t.accent};
    font-size: 13px;
    font-weight: 700;
    min-width: 20px;
    padding: 1px 8px;
    border: 1px solid {t.accent};
    border-radius: 10px;
    background-color: rgba(128, 128, 128, 0.08);
}}
QLabel#RadarResonanceEmpty {{
    color: {t.text_muted};
    font-size: 12px;
    line-height: 1.4;
    padding: 8px 4px;
}}
QListWidget#RadarResonanceList {{
    background: transparent;
    border: none;
    color: {t.text_primary};
    font-size: 12px;
    outline: none;
    selection-background-color: transparent;
    selection-color: {t.text_primary};
    show-decoration-selected: 0;
}}
QListWidget#RadarResonanceList::item {{
    background: transparent;
    border: none;
    padding: 0;
    margin-bottom: 4px;
}}
QListWidget#RadarResonanceList::item:selected,
QListWidget#RadarResonanceList::item:selected:active,
QListWidget#RadarResonanceList::item:selected:!active {{
    background: transparent;
}}
QFrame#RadarResonanceRow {{
    background-color: {t.index_ticker_bg};
    border: 1px solid {t.panel_border};
    border-radius: 6px;
}}
QFrame#RadarResonanceRow[selected="true"] {{
    border-color: {t.accent};
    background-color: {t.index_ticker_bg};
}}
QFrame#RadarResonanceRow:hover {{
    border-color: {t.accent};
}}
QLabel#RadarResonanceRowName {{
    color: {t.text_primary};
    font-size: 13px;
    font-weight: 600;
}}
QLabel#RadarResonanceRowSymbol {{
    color: {t.text_muted};
    font-size: 11px;
    padding-left: 16px;
}}
QLabel#RadarResonanceRowPrice {{
    color: {t.text_primary};
    font-size: 13px;
    font-weight: 600;
}}
QLabel#RadarResonanceCountChip {{
    color: {t.accent};
    font-size: 10px;
    font-weight: 600;
    padding: 1px 6px;
    border: 1px solid {t.accent};
    border-radius: 4px;
    background-color: rgba(128, 128, 128, 0.08);
}}
QLabel#RadarResonanceRowCards {{
    color: {t.text_muted};
    font-size: 10px;
}}
QPushButton#RadarResonanceAddAll,
QPushButton#RadarResonanceAi,
QPushButton#RadarResonanceScreener,
QPushButton#RadarResonanceWeights {{
    font-size: 11px;
    padding: 5px 8px;
    min-height: 24px;
}}
QPushButton#RadarResonanceAddAll,
QPushButton#RadarResonanceAi {{
    font-weight: 600;
}}
"""


def build_watchlist_multiview_stylesheet(t: ThemeTokens) -> str:
    return f"""
QWidget#WatchlistMultiViewBoard {{
    background-color: {t.app_bg};
}}
QLabel#WatchlistMultiSummary {{
    color: {t.text_secondary};
    font-size: 12px;
    padding: 4px 12px 0 12px;
}}
QLabel#WatchlistMultiEmpty {{
    color: {t.text_muted};
    font-size: 13px;
    padding: 24px;
}}
QScrollArea#WatchlistMultiScroll {{
    background: transparent;
    border: none;
}}
QWidget#WatchlistMultiGridHost {{
    background: transparent;
}}
QFrame#WatchlistMultiCard {{
    background-color: {t.index_ticker_bg};
    border: 1px solid {t.panel_border};
    border-radius: 8px;
}}
QFrame#WatchlistMultiCard:hover {{
    border-color: {t.accent};
}}
QFrame#WatchlistMultiCard[selected="true"] {{
    border-color: {t.accent};
    background-color: {t.panel_bg};
}}
QLabel#WatchlistMultiAnomalyBadge {{
    color: {t.accent};
    font-size: 10px;
    min-width: 10px;
}}
QLabel#WatchlistMultiName {{
    color: {t.text_primary};
    font-size: 14px;
    font-weight: 600;
}}
QLabel#WatchlistMultiSymbol {{
    color: {t.text_muted};
    font-size: 11px;
}}
QLabel#WatchlistMultiPrice {{
    color: {t.text_primary};
    font-size: 14px;
    font-weight: 600;
}}
QLabel#WatchlistMultiMetricChip,
QLabel#WatchlistMultiSubChip {{
    color: {t.text_secondary};
    font-size: 11px;
}}
QLabel#WatchlistMultiSignalBadge,
QLabel#WatchlistMultiPositionBadge,
QLabel#WatchlistMultiSectorBadge {{
    color: {t.text_secondary};
    font-size: 10px;
    padding: 1px 6px;
    border: 1px solid {t.panel_border};
    border-radius: 4px;
}}
QLabel#WatchlistMultiSparklineKind {{
    color: {t.text_muted};
    font-size: 10px;
    padding-top: 2px;
}}
QWidget#WatchlistMultiSparkline {{
    background: transparent;
}}
QWidget#WatchlistMultiHeader {{
    background: transparent;
}}
QComboBox#WatchlistMultiSortCombo {{
    min-width: 76px;
    max-width: 88px;
}}
QComboBox#WatchlistMultiColumnsCombo {{
    min-width: 52px;
    max-width: 64px;
}}
"""


def build_sector_flow_stylesheet(t: ThemeTokens) -> str:
    return f"""
QWidget#SectorFlowPanel {{
    background-color: {t.app_bg};
}}
QLabel#SectorFlowSummary {{
    color: {t.text_secondary};
    font-size: 12px;
}}
QTableWidget#SectorFlowTable,
QTableWidget#SectorFlowLeaderTable {{
    background-color: {t.panel_bg};
    border: 1px solid {t.panel_border};
    gridline-color: {t.panel_border};
}}
QFrame#SectorFlowDetailPanel {{
    background-color: {t.panel_bg};
    border: 1px solid {t.panel_border};
    border-radius: 6px;
}}
QWidget#SectorFlowMiniBar {{
    background-color: transparent;
}}
QSplitter#SectorFlowSplitter::handle {{
    background-color: {t.panel_border};
    width: 1px;
}}
"""


def build_watchlist_group_tab_stylesheet(t: ThemeTokens) -> str:
    return f"""
QWidget#WatchlistGroupTabBar {{
    background-color: transparent;
}}
QPushButton#WatchlistGroupTab {{
    background-color: {t.tab_bg};
    color: {t.tab_text};
    border: 1px solid {t.tab_border};
    border-radius: 4px;
    padding: 4px 12px;
    font-size: 12px;
    min-height: 24px;
}}
QPushButton#WatchlistGroupTab:checked {{
    background-color: {t.tab_selected_bg};
    color: {t.tab_selected_text};
    border-color: {t.tab_selected_border};
}}
QPushButton#WatchlistGroupTab:hover {{
    color: {t.tab_hover_text};
}}
QPushButton#WatchlistGroupAddButton {{
    background-color: {t.panel_bg};
    color: {t.accent};
    border: 1px solid {t.accent_soft};
    border-radius: 4px;
    padding: 4px 12px;
    font-size: 12px;
    font-weight: 600;
    min-height: 24px;
}}
QPushButton#WatchlistGroupAddButton:hover:enabled {{
    background-color: {t.accent};
    color: {t.action_btn_text};
    border-color: {t.accent};
}}
QPushButton#WatchlistGroupAddButton:pressed:enabled {{
    background-color: {t.accent_hover};
    border-color: {t.accent_hover};
}}
QPushButton#WatchlistGroupAddButton:disabled {{
    color: {t.text_muted};
    background-color: {t.panel_bg};
    border-color: {t.panel_border};
}}
QFrame#WatchlistGroupTabSeparator {{
    color: {t.panel_border};
    max-height: 20px;
}}
"""


def build_watchlist_group_dialog_stylesheet(t: ThemeTokens) -> str:
    return f"""
QDialog#WatchlistGroupDialog {{
    background-color: {t.app_bg};
    color: {t.text_primary};
}}
QLabel#WatchlistGroupDialogTitle {{
    color: {t.text_primary};
    font-size: 15px;
    font-weight: 600;
}}
QLabel#SettingsHint {{
    color: {t.text_secondary};
    font-size: 12px;
    padding: 8px 10px;
    background-color: {t.panel_bg};
    border: 1px solid {t.panel_border};
    border-radius: 6px;
}}
QLabel#SettingsMeta {{
    color: {t.text_muted};
    font-size: 12px;
}}
QListWidget#WatchlistGroupList {{
    background-color: {t.panel_bg};
    border: 1px solid {t.panel_border};
    border-radius: 8px;
    padding: 4px;
    color: {t.text_primary};
    font-size: 13px;
    outline: none;
}}
QListWidget#WatchlistGroupList::item {{
    padding: 8px 10px;
    border-radius: 6px;
}}
QListWidget#WatchlistGroupList::item:hover {{
    background-color: {t.menu_selected_bg};
}}
QListWidget#WatchlistGroupList::item:selected {{
    background-color: {t.menu_selected_bg};
    color: {t.text_primary};
}}
"""


def build_insight_rank_stylesheet(t: ThemeTokens) -> str:
    """Deprecated: use build_radar_stylesheet."""
    return build_radar_stylesheet(t)
