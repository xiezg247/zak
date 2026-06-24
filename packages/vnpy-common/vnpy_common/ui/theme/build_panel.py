"""面板级通用 QSS：卡片、指标块、数据表、Document Tab。"""

from __future__ import annotations

from vnpy_common.ui.theme.tokens import ThemeTokens


def build_panel_stylesheet(tokens: ThemeTokens) -> str:
    t = tokens
    return f"""
QFrame#ContentCard {{
    background-color: {t.panel_bg};
    border: 1px solid {t.panel_border};
    border-radius: 8px;
}}
QFrame#MetricTile {{
    background-color: {t.depth_bg};
    border: 1px solid {t.panel_border};
    border-radius: 6px;
}}
QLabel#MetricTileTitle {{
    color: {t.text_muted};
    font-size: 11px;
}}
QLabel#MetricTileValue {{
    color: {t.text_primary};
    font-size: 17px;
    font-weight: 600;
}}
QLabel#MetricTileSub {{
    color: {t.text_hint};
    font-size: 11px;
}}
QTabWidget#DocumentTabWidget > QTabBar::tab {{
    padding: 8px 18px;
    margin-right: 4px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
}}
QTabWidget#DocumentTabWidget::pane {{
    border: none;
    border-radius: 0;
    top: 0px;
    margin: 0;
    padding: 0;
    background-color: {t.app_bg};
}}
QTabWidget#DocumentTabWidget > QTabBar {{
    border: none;
    background: transparent;
}}
QWidget#PanelFooter {{
    border-top: 1px solid {t.panel_border};
    padding-top: 4px;
}}
QLabel#PanelStatus[loading="true"] {{
    color: {t.accent};
    font-weight: 600;
}}
"""


def build_stock_analysis_stylesheet(tokens: ThemeTokens) -> str:
    """个股分析弹窗附加 QSS（面板通用样式见 build_panel_stylesheet）。"""
    t = tokens
    return f"""
QDialog#StockAnalysisDialog {{
    background-color: {t.app_bg};
}}
QWidget#StockAnalysisHeader {{
    background-color: {t.panel_bg};
    border: 1px solid {t.panel_border};
    border-radius: 8px;
}}
QLabel#StockAnalysisSymbol {{
    color: {t.accent};
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.5px;
}}
QLabel#StockAnalysisName {{
    color: {t.text_primary};
    font-size: 18px;
    font-weight: 600;
}}
QLabel#StockAnalysisCode {{
    color: {t.text_muted};
    font-size: 12px;
}}
QLabel#StockAnalysisPrice {{
    font-size: 28px;
    font-weight: 700;
}}
QLabel#StockAnalysisChange {{
    font-size: 14px;
    font-weight: 600;
    padding: 2px 8px;
    border-radius: 4px;
}}
QDialog#StockAnalysisDialog QTabWidget,
QDialog#StockAnalysisDialog QTabWidget::tab-bar {{
    border: none;
    background: transparent;
}}
QDialog#StockAnalysisDialog QTabWidget::pane {{
    border: none;
    top: 0px;
    margin: 0;
    padding: 0;
    background-color: {t.app_bg};
}}
QDialog#StockAnalysisDialog QTabBar {{
    border: none;
    background: transparent;
    qproperty-drawBase: 0;
}}
QDialog#StockAnalysisDialog QTabBar::tab {{
    background-color: {t.tab_bg};
    color: {t.tab_text};
    border: 1px solid {t.tab_border};
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    padding: 8px 16px;
    margin-right: 4px;
}}
QDialog#StockAnalysisDialog QTabBar::tab:selected {{
    background-color: {t.tab_selected_bg};
    color: {t.tab_selected_text};
    border-color: {t.tab_selected_border};
}}
QDialog#StockAnalysisDialog QTabBar::tab:hover {{
    color: {t.tab_hover_text};
}}
QLabel#OverviewScreeningBadge {{
    color: {t.accent};
    font-weight: 600;
    padding: 4px 8px;
    border-radius: 4px;
    background-color: {t.accent_soft};
}}
QSplitter#StockAnalysisBodySplitter {{
    border: none;
    background: transparent;
}}
QWidget#StockAnalysisAiSidebar {{
    background-color: {t.panel_bg};
    border-left: 1px solid {t.panel_border};
}}
QLabel#StockAnalysisAiTitle {{
    color: {t.text_primary};
    font-size: 13px;
    font-weight: 600;
}}
QLabel#StockAnalysisAiPlaceholder {{
    color: {t.text_muted};
    font-size: 12px;
    padding: 16px;
}}
QPushButton#OverviewReadinessChip {{
    padding: 4px 10px;
    border-radius: 4px;
    border: 1px solid {t.panel_border};
    background-color: {t.panel_bg};
    color: {t.text_secondary};
    font-size: 12px;
}}
QPushButton#OverviewReadinessChip[readiness_status="ready"] {{
    border-color: {t.semantic_success};
    color: {t.semantic_success};
}}
QPushButton#OverviewReadinessChip[readiness_status="partial"] {{
    border-color: {t.semantic_warning};
    color: {t.semantic_warning};
}}
QPushButton#OverviewReadinessChip[readiness_status="missing"] {{
    border-color: {t.semantic_error};
    color: {t.semantic_error};
}}
QPushButton#OverviewReadinessChip[readiness_status="unconfigured"] {{
    border-color: {t.text_muted};
    color: {t.text_muted};
}}
QPushButton#OverviewAlertLink {{
    text-align: left;
    padding: 2px 0;
    border: none;
    background: transparent;
    color: {t.text_secondary};
    font-size: 12px;
}}
QPushButton#OverviewAlertLink[alert_severity="warn"] {{
    color: {t.semantic_warning};
}}
QPushButton#OverviewAlertLink:hover {{
    color: {t.accent};
}}
QWidget#OverviewAlertRow {{
    background: transparent;
}}
QLabel#OverviewAlertText {{
    color: {t.text_secondary};
    font-size: 12px;
    padding: 2px 0;
    background: transparent;
}}
QLabel#OverviewAlertText[alert_severity="warn"] {{
    color: {t.semantic_warning};
}}
QWidget#OverviewAlertRow[alert_severity="warn"] QLabel#OverviewAlertText {{
    color: {t.semantic_warning};
}}
QWidget#OverviewAlertRow[clickable="true"]:hover QLabel#OverviewAlertText {{
    color: {t.accent};
}}
"""
