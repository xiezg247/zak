"""由 ThemeTokens 生成图表区 QSS 与 pyqtgraph 调色板。"""

from __future__ import annotations

from dataclasses import dataclass

from vnpy_common.ui.theme.tokens import DARK_TOKENS, ThemeTokens

GRID_ALPHA = 0.12
AVG_LINE_COLOR = "#e6b422"
PREV_CLOSE_COLOR = "#888888"
INTRADAY_LAST_DOT_SIZE = 7
INTRADAY_PRICE_LINE_WIDTH = 2.0
INTRADAY_AVG_LINE_WIDTH = 1.2


@dataclass(frozen=True)
class ChartPalette:
    bg: str
    panel_bg: str
    border: str
    hint_text: str
    legend_bg: str
    legend_border: str
    axis_color: str
    axis_text: str
    crosshair: str
    lunch_line: str
    info_text: str
    tab_bg: str
    tab_text: str
    tab_selected_bg: str
    tab_selected_text: str
    tab_border: str
    tab_hover_text: str
    combo_bg: str
    combo_border: str
    combo_text: str
    combo_popup_bg: str
    combo_selection_bg: str


def chart_palette(t: ThemeTokens) -> ChartPalette:
    return ChartPalette(
        bg=t.app_bg,
        panel_bg=t.depth_bg,
        border=t.table_grid,
        hint_text=t.text_muted,
        legend_bg=t.app_bg,
        legend_border=t.header_bg,
        axis_color=t.text_hint,
        axis_text=t.header_text,
        crosshair=t.text_hint,
        lunch_line=t.table_grid,
        info_text=t.text_secondary,
        tab_bg=t.tab_bg,
        tab_text=t.tab_text,
        tab_selected_bg=t.tab_selected_bg,
        tab_selected_text=t.tab_selected_text,
        tab_border=t.tab_border,
        tab_hover_text=t.tab_hover_text,
        combo_bg=t.combo_bg,
        combo_border=t.combo_border,
        combo_text=t.combo_text,
        combo_popup_bg=t.combo_popup_bg,
        combo_selection_bg=t.combo_selection_bg,
    )


def build_chart_frame_stylesheet(t: ThemeTokens) -> str:
    p = chart_palette(t)
    return f"""
QWidget#ChartFrame {{
    background-color: {p.panel_bg};
    border: 1px solid {p.border};
    border-radius: 4px;
}}
QLabel#ChartHint {{
    color: {p.hint_text};
    font-size: 13px;
}}
QWidget#MaLegendBar,
QWidget#ReferenceLineLegendBar {{
    background-color: {p.legend_bg};
    border-bottom: 1px solid {p.legend_border};
    font-size: 11px;
}}
"""


def build_intraday_info_stylesheet(t: ThemeTokens) -> str:
    p = chart_palette(t)
    return f"""
QLabel#IntradayInfoBar {{
    color: {p.info_text};
    font-size: 11px;
    padding: 2px 6px;
    background-color: transparent;
}}
"""


def build_chart_panel_stylesheet(t: ThemeTokens) -> str:
    p = chart_palette(t)
    return (
        build_chart_frame_stylesheet(t)
        + f"""
QWidget#ChartPanel {{
    background-color: {p.panel_bg};
    border: 1px solid {p.border};
    border-radius: 4px;
}}
QTabBar::tab {{
    background-color: {p.tab_bg};
    color: {p.tab_text};
    border: 1px solid {p.tab_border};
    border-bottom: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    padding: 5px 14px;
    margin-right: 2px;
    font-size: 12px;
}}
QTabBar::tab:selected {{
    background-color: {p.tab_selected_bg};
    color: {p.tab_selected_text};
    border-color: {p.tab_border};
}}
QTabBar::tab:hover {{
    color: {p.tab_hover_text};
}}
QComboBox {{
    background-color: {p.combo_bg};
    border: 1px solid {p.combo_border};
    border-radius: 3px;
    color: {p.combo_text};
    padding: 3px 8px;
    font-size: 12px;
    min-width: 56px;
}}
QComboBox::drop-down {{
    border: none;
    width: 18px;
}}
QComboBox QAbstractItemView {{
    background-color: {p.combo_popup_bg};
    color: {p.combo_text};
    selection-background-color: {p.combo_selection_bg};
    border: 1px solid {p.combo_border};
}}
"""
    )


_DARK = chart_palette(DARK_TOKENS)
CHART_BG = _DARK.bg
CHART_PANEL_BG = _DARK.panel_bg
AXIS_COLOR = _DARK.axis_color
AXIS_TEXT_COLOR = _DARK.axis_text
INTRADAY_CROSSHAIR_COLOR = _DARK.crosshair
INTRADAY_LUNCH_LINE_COLOR = _DARK.lunch_line
INTRADAY_INFO_COLOR = _DARK.info_text

CHART_FRAME_STYLESHEET = build_chart_frame_stylesheet(DARK_TOKENS)
CHART_PANEL_STYLESHEET = build_chart_panel_stylesheet(DARK_TOKENS)
INTRADAY_INFO_STYLESHEET = build_intraday_info_stylesheet(DARK_TOKENS)
