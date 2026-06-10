"""终端 UI 主题（深色 / 浅色切换）。"""

from vnpy_ashare.ui.theme.build import build_terminal_stylesheet, stylesheet_for
from vnpy_ashare.ui.theme.build_ai import (
    build_ai_floating_stylesheet,
    build_ai_panel_stylesheet,
    build_ai_tools_stylesheet,
    build_ai_trace_stylesheet,
)
from vnpy_ashare.ui.theme.build_chart import (
    build_chart_frame_stylesheet,
    build_chart_panel_stylesheet,
    build_intraday_info_stylesheet,
    chart_palette,
)
from vnpy_ashare.ui.theme.build_extra import (
    build_legacy_page_stylesheet,
    build_scheduler_page_stylesheet,
    build_scheduler_table_stylesheet,
    build_settings_stylesheet,
    format_scheduler_empty_html,
    format_scheduler_run_log_html,
)
from vnpy_ashare.ui.theme.manager import ExtraStyles, ThemeManager, theme_manager
from vnpy_ashare.ui.theme.orb_palette import OrbPalette, orb_palette
from vnpy_ashare.ui.theme.html_palette import HtmlPalette, html_palette
from vnpy_ashare.ui.theme.market_colors import MarketColors, market_colors
from vnpy_ashare.ui.theme.tokens import DEFAULT_THEME, DEFAULT_THEME_PREFERENCE, ThemeId, ThemePreference, ThemeTokens, get_tokens

__all__ = [
    "DEFAULT_THEME",
    "DEFAULT_THEME_PREFERENCE",
    "ExtraStyles",
    "ThemeId",
    "ThemeManager",
    "ThemePreference",
    "ThemeTokens",
    "build_ai_floating_stylesheet",
    "build_ai_panel_stylesheet",
    "build_ai_tools_stylesheet",
    "build_ai_trace_stylesheet",
    "build_chart_frame_stylesheet",
    "build_chart_panel_stylesheet",
    "build_intraday_info_stylesheet",
    "build_legacy_page_stylesheet",
    "build_scheduler_page_stylesheet",
    "build_scheduler_table_stylesheet",
    "build_settings_stylesheet",
    "build_terminal_stylesheet",
    "chart_palette",
    "format_scheduler_empty_html",
    "format_scheduler_run_log_html",
    "get_tokens",
    "HtmlPalette",
    "html_palette",
    "MarketColors",
    "market_colors",
    "orb_palette",
    "OrbPalette",
    "stylesheet_for",
    "theme_manager",
]
