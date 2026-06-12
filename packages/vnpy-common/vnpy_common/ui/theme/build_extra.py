"""由 ThemeTokens 生成页面/对话框附加 QSS。"""

from __future__ import annotations

import html

from vnpy_common.ui.theme.tokens import ThemeTokens


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
    min-width: 108px;
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


def build_legacy_page_stylesheet(t: ThemeTokens) -> str:
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


def format_scheduler_run_log_html(t: ThemeTokens, records: list[object]) -> str:
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
    return f"""
QWidget#MarketOverviewPanel {{
    background-color: {t.index_ticker_bg};
}}
QLabel#MarketBreadthBar {{
    background-color: {t.index_ticker_bg};
    color: {t.index_ticker_text};
    padding: 6px 12px;
    font-size: 12px;
}}
QScrollArea#IndexCardScroll {{
    background-color: {t.index_ticker_bg};
    border: none;
}}
QWidget#IndexCardHost {{
    background-color: transparent;
}}
QFrame#IndexCard {{
    background-color: {t.panel_bg};
    border: 1px solid {t.panel_border};
    border-radius: 6px;
    min-width: 108px;
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
    font-size: 15px;
    font-weight: 600;
}}
QLabel#IndexCardPct {{
    font-size: 12px;
    font-weight: 600;
}}
QLabel#MarketEnvBadge {{
    background-color: {t.panel_bg};
    border: 1px solid {t.panel_border};
    border-radius: 4px;
    padding: 2px 8px;
    color: {t.text_secondary};
    font-size: 11px;
}}
QPushButton#OverviewTabButton {{
    background-color: transparent;
    border: 1px solid {t.panel_border};
    border-radius: 4px;
    padding: 2px 10px;
    color: {t.text_secondary};
    font-size: 11px;
}}
QPushButton#OverviewTabButton:checked {{
    background-color: {t.panel_bg};
    color: {t.text_primary};
    border-color: {t.accent};
}}
QScrollArea#SectorCardScroll {{
    background-color: {t.index_ticker_bg};
    border: none;
}}
QWidget#SectorCardHost {{
    background-color: transparent;
}}
QFrame#SectorCard {{
    background-color: {t.panel_bg};
    border: 1px solid {t.panel_border};
    border-radius: 6px;
    min-width: 96px;
}}
QFrame#SectorCard:hover {{
    border-color: {t.accent};
}}
QLabel#SectorCardName {{
    color: {t.text_secondary};
    font-size: 11px;
}}
QLabel#SectorCardPct {{
    font-size: 14px;
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
"""


def build_radar_stylesheet(t: ThemeTokens) -> str:
    return f"""
QFrame#RadarCard {{
    background-color: {t.panel_bg};
    border: 1px solid {t.panel_border};
    border-radius: 8px;
}}
QScrollArea#RadarCardScroll {{
    background: transparent;
    border: none;
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
    background-color: {t.panel_bg};
    border: 1px solid {t.panel_border};
    border-radius: 4px;
    padding: 2px 6px;
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
}}
QLabel#RadarCardEmpty {{
    color: {t.text_muted};
    font-size: 12px;
    padding: 12px 8px;
}}
QLabel#RadarCardMeta {{
    color: {t.text_muted};
    font-size: 11px;
}}
QPushButton#RadarCardViewRun {{
    color: {t.accent};
    font-size: 11px;
    padding: 0 4px;
}}
QPushButton#RadarCardAddAll {{
    color: {t.accent};
    font-size: 11px;
    padding: 0 4px;
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
    min-width: 88px;
}}
QToolButton#RadarCardRefresh {{
    color: {t.text_muted};
    border: none;
    padding: 0 4px;
    font-size: 14px;
}}
QToolButton#RadarCardRefresh:hover {{
    color: {t.accent};
}}
QToolButton#RadarCardRefresh:disabled {{
    color: {t.text_muted};
}}
QFrame#RadarResonancePanel {{
    background-color: {t.panel_bg};
    border-left: 1px solid {t.panel_border};
}}
QLabel#RadarResonanceTitle {{
    color: {t.text_primary};
    font-size: 13px;
    font-weight: 600;
}}
QLabel#RadarResonanceCount {{
    color: {t.accent};
    font-size: 13px;
    font-weight: 600;
}}
QLabel#RadarResonanceEmpty {{
    color: {t.text_muted};
    font-size: 12px;
    padding: 16px 8px;
}}
QListWidget#RadarResonanceList {{
    background: transparent;
    border: none;
    color: {t.text_primary};
    font-size: 12px;
}}
QListWidget#RadarResonanceList::item {{
    padding: 8px 4px;
    border-bottom: 1px solid {t.panel_border};
}}
QListWidget#RadarResonanceList::item:selected {{
    background-color: {t.menu_selected_bg};
}}
QPushButton#RadarResonanceAddAll,
QPushButton#RadarResonanceAi {{
    font-size: 11px;
}}
"""


def build_insight_rank_stylesheet(t: ThemeTokens) -> str:
    """Deprecated: use build_radar_stylesheet."""
    return build_radar_stylesheet(t)
