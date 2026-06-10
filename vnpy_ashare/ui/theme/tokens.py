"""终端 UI 主题 Design Tokens（深色 / 浅色）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ThemeId = Literal["dark", "light"]

THEME_IDS: tuple[ThemeId, ...] = ("dark", "light")
DEFAULT_THEME: ThemeId = "dark"


@dataclass(frozen=True)
class ThemeTokens:
    id: ThemeId
    app_bg: str
    nav_bg: str
    nav_muted: str
    nav_text: str
    nav_text_hover: str
    nav_hover_bg: str
    nav_selected_bg: str
    nav_separator: str
    splitter_handle: str
    accent: str
    accent_hover: str
    accent_soft: str
    table_bg: str
    table_grid: str
    table_alt: str
    table_hover: str
    table_selected: str
    header_bg: str
    header_text: str
    header_border: str
    input_bg: str
    input_border: str
    input_text: str
    input_disabled_bg: str
    input_disabled_text: str
    btn_bg: str
    btn_border: str
    btn_text: str
    btn_hover_bg: str
    btn_disabled_text: str
    secondary_btn_bg: str
    secondary_btn_border: str
    secondary_btn_text: str
    secondary_btn_hover_bg: str
    secondary_btn_hover_border: str
    secondary_btn_hover_text: str
    secondary_btn_pressed_bg: str
    danger_btn_bg: str
    danger_btn_border: str
    danger_btn_text: str
    danger_btn_hover_bg: str
    danger_btn_hover_border: str
    danger_btn_hover_text: str
    action_btn_bg: str
    action_btn_border: str
    action_btn_text: str
    action_btn_hover_bg: str
    action_btn_hover_border: str
    action_btn_pressed_bg: str
    action_btn_disabled_bg: str
    action_btn_disabled_border: str
    action_btn_disabled_text: str
    text_primary: str
    text_secondary: str
    text_muted: str
    text_hint: str
    text_section: str
    text_section_alt: str
    panel_bg: str
    panel_border: str
    depth_bg: str
    depth_text: str
    depth_table_bg: str
    depth_table_text: str
    diagnose_bg: str
    diagnose_border: str
    index_ticker_bg: str
    index_ticker_text: str
    combo_bg: str
    combo_border: str
    combo_text: str
    combo_hover_bg: str
    combo_hover_border: str
    combo_disabled_bg: str
    combo_disabled_text: str
    combo_popup_bg: str
    combo_popup_border: str
    combo_selection_bg: str
    combo_item_hover_bg: str
    screener_form_bg: str
    screener_form_border: str
    screener_form_text: str
    screener_log_bg: str
    screener_log_border: str
    screener_log_text: str
    statusbar_bg: str
    statusbar_border: str
    statusbar_text: str
    tab_bg: str
    tab_text: str
    tab_border: str
    tab_selected_bg: str
    tab_selected_text: str
    tab_selected_border: str
    tab_hover_text: str
    run_row_active_bg: str
    run_row_hover_bg: str
    run_row_title: str
    run_row_subtitle: str
    run_row_unread: str
    checkbox_border: str
    checkbox_bg: str
    toolbar_sep: str
    menu_bg: str
    menu_text: str
    menu_border: str
    menu_selected_bg: str
    menu_selected_text: str
    semantic_success: str
    semantic_warning: str
    semantic_error: str


DARK_TOKENS = ThemeTokens(
    id="dark",
    app_bg="#1a1a1a",
    nav_bg="#0f0f12",
    nav_muted="#6a6a6a",
    nav_text="#8a8a8a",
    nav_text_hover="#b8b8b8",
    nav_hover_bg="#1c1c22",
    nav_selected_bg="#1a2438",
    nav_separator="#2a2a30",
    splitter_handle="#252528",
    accent="#4a9eff",
    accent_hover="#6ab4ff",
    accent_soft="#3d6a9e",
    table_bg="#1a1a1a",
    table_grid="#2a2a2a",
    table_alt="#1e1e22",
    table_hover="#242428",
    table_selected="#2a4a7a",
    header_bg="#252525",
    header_text="#a0a0a0",
    header_border="#333333",
    input_bg="#252525",
    input_border="#3a3a3a",
    input_text="#e0e0e0",
    input_disabled_bg="#1f1f1f",
    input_disabled_text="#777777",
    btn_bg="#2d2d2d",
    btn_border="#444444",
    btn_text="#e0e0e0",
    btn_hover_bg="#3a3a3a",
    btn_disabled_text="#666666",
    secondary_btn_bg="#2a2a2a",
    secondary_btn_border="#3a3a3a",
    secondary_btn_text="#b0b0b0",
    secondary_btn_hover_bg="#353535",
    secondary_btn_hover_border="#555555",
    secondary_btn_hover_text="#e0e0e0",
    secondary_btn_pressed_bg="#222222",
    danger_btn_bg="#2a2020",
    danger_btn_border="#6a3030",
    danger_btn_text="#ff8a8a",
    danger_btn_hover_bg="#3a2828",
    danger_btn_hover_border="#8a4040",
    danger_btn_hover_text="#ffaaaa",
    action_btn_bg="#2a5a9e",
    action_btn_border="#4a9eff",
    action_btn_text="#ffffff",
    action_btn_hover_bg="#3a6fbf",
    action_btn_hover_border="#6ab4ff",
    action_btn_pressed_bg="#1e4a80",
    action_btn_disabled_bg="#1a3a60",
    action_btn_disabled_border="#3a5a80",
    action_btn_disabled_text="#6688aa",
    text_primary="#e8e8e8",
    text_secondary="#8a8a8a",
    text_muted="#6a6a7a",
    text_hint="#5a5a6a",
    text_section="#8a8aaf",
    text_section_alt="#7a7a8f",
    panel_bg="#1e1e22",
    panel_border="#2d2d32",
    depth_bg="#141414",
    depth_text="#a0a0a0",
    depth_table_bg="#1a1a1a",
    depth_table_text="#d0d0d0",
    diagnose_bg="#1e1e22",
    diagnose_border="#2d2d32",
    index_ticker_bg="#141414",
    index_ticker_text="#d0d0d0",
    combo_bg="#252525",
    combo_border="#4a4a4a",
    combo_text="#f0f0f0",
    combo_hover_bg="#2c2c2c",
    combo_hover_border="#5a8fd4",
    combo_disabled_bg="#1f1f1f",
    combo_disabled_text="#777777",
    combo_popup_bg="#2a2a2a",
    combo_popup_border="#4a4a4a",
    combo_selection_bg="#3d6a9e",
    combo_item_hover_bg="#383838",
    screener_form_bg="#1e1e22",
    screener_form_border="#2d2d32",
    screener_form_text="#a0a0a0",
    screener_log_bg="#141418",
    screener_log_border="#2a2a30",
    screener_log_text="#a8a8b0",
    statusbar_bg="#1a1a20",
    statusbar_border="#2a2a2a",
    statusbar_text="#888888",
    tab_bg="#252525",
    tab_text="#9090a0",
    tab_border="#3a3a3a",
    tab_selected_bg="#1e1e22",
    tab_selected_text="#e0e0e0",
    tab_selected_border="#4a4a4a",
    tab_hover_text="#c8c8c8",
    run_row_active_bg="#1a2438",
    run_row_hover_bg="#1e1e28",
    run_row_title="#d0d0d8",
    run_row_subtitle="#6a6a72",
    run_row_unread="#7dd3fc",
    checkbox_border="#4a4a55",
    checkbox_bg="#1a1a22",
    toolbar_sep="#3a3a3a",
    menu_bg="#1e1e22",
    menu_text="#e0e0e0",
    menu_border="#3a3a3a",
    menu_selected_bg="#2a4a7a",
    menu_selected_text="#ffffff",
    semantic_success="#3ddc84",
    semantic_warning="#f2c94c",
    semantic_error="#ff4d4f",
)

LIGHT_TOKENS = ThemeTokens(
    id="light",
    app_bg="#e6e8ee",
    nav_bg="#dde0e8",
    nav_muted="#7a8090",
    nav_text="#4a5060",
    nav_text_hover="#1c1c22",
    nav_hover_bg="#d0d4de",
    nav_selected_bg="#cdd9f5",
    nav_separator="#c4c8d4",
    splitter_handle="#b8bcc8",
    accent="#2563eb",
    accent_hover="#1d4ed8",
    accent_soft="#3b82f6",
    table_bg="#eef0f5",
    table_grid="#d4d8e2",
    table_alt="#e4e7ef",
    table_hover="#dde4f5",
    table_selected="#c8d8f8",
    header_bg="#dfe3eb",
    header_text="#4a5060",
    header_border="#c8ccd6",
    input_bg="#f2f4f8",
    input_border="#c4c8d4",
    input_text="#1c1c22",
    input_disabled_bg="#e4e7ef",
    input_disabled_text="#9098a8",
    btn_bg="#e8ebf1",
    btn_border="#c4c8d4",
    btn_text="#1c1c22",
    btn_hover_bg="#dfe3eb",
    btn_disabled_text="#9098a8",
    secondary_btn_bg="#e4e7ef",
    secondary_btn_border="#c4c8d4",
    secondary_btn_text="#4a5060",
    secondary_btn_hover_bg="#d8dce6",
    secondary_btn_hover_border="#a8aeb8",
    secondary_btn_hover_text="#1c1c22",
    secondary_btn_pressed_bg="#cdd2dc",
    danger_btn_bg="#fce8e8",
    danger_btn_border="#f5a8a8",
    danger_btn_text="#c62828",
    danger_btn_hover_bg="#fad4d4",
    danger_btn_hover_border="#ef8888",
    danger_btn_hover_text="#a61e1e",
    action_btn_bg="#2563eb",
    action_btn_border="#2563eb",
    action_btn_text="#ffffff",
    action_btn_hover_bg="#1d4ed8",
    action_btn_hover_border="#1d4ed8",
    action_btn_pressed_bg="#1e40af",
    action_btn_disabled_bg="#93c5fd",
    action_btn_disabled_border="#93c5fd",
    action_btn_disabled_text="#eff6ff",
    text_primary="#1c1c22",
    text_secondary="#4a5060",
    text_muted="#6a7080",
    text_hint="#7a8090",
    text_section="#4a5070",
    text_section_alt="#5a6080",
    panel_bg="#e8ebf1",
    panel_border="#c8ccd6",
    depth_bg="#e0e3ea",
    depth_text="#4a5060",
    depth_table_bg="#eef0f5",
    depth_table_text="#1c1c22",
    diagnose_bg="#e8ebf1",
    diagnose_border="#c8ccd6",
    index_ticker_bg="#dfe3eb",
    index_ticker_text="#3a4050",
    combo_bg="#f2f4f8",
    combo_border="#c4c8d4",
    combo_text="#1c1c22",
    combo_hover_bg="#e8ebf1",
    combo_hover_border="#2563eb",
    combo_disabled_bg="#e4e7ef",
    combo_disabled_text="#9098a8",
    combo_popup_bg="#eef0f5",
    combo_popup_border="#c4c8d4",
    combo_selection_bg="#2563eb",
    combo_item_hover_bg="#dde4f5",
    screener_form_bg="#e8ebf1",
    screener_form_border="#c8ccd6",
    screener_form_text="#4a5060",
    screener_log_bg="#dfe3eb",
    screener_log_border="#c8ccd6",
    screener_log_text="#4a5060",
    statusbar_bg="#dfe3eb",
    statusbar_border="#c8ccd6",
    statusbar_text="#5a6070",
    tab_bg="#dfe3eb",
    tab_text="#5a6070",
    tab_border="#c4c8d4",
    tab_selected_bg="#eef0f5",
    tab_selected_text="#1c1c22",
    tab_selected_border="#c4c8d4",
    tab_hover_text="#2c3038",
    run_row_active_bg="#cdd9f5",
    run_row_hover_bg="#dde4f5",
    run_row_title="#1c1c22",
    run_row_subtitle="#6a7080",
    run_row_unread="#0284c7",
    checkbox_border="#a0a8b4",
    checkbox_bg="#f2f4f8",
    toolbar_sep="#c0c4d0",
    menu_bg="#e4e7ef",
    menu_text="#1c1c22",
    menu_border="#c4c8d4",
    menu_selected_bg="#c8d8f8",
    menu_selected_text="#1c1c22",
    semantic_success="#16a34a",
    semantic_warning="#ca8a04",
    semantic_error="#dc2626",
)

_TOKENS: dict[ThemeId, ThemeTokens] = {
    "dark": DARK_TOKENS,
    "light": LIGHT_TOKENS,
}


def get_tokens(theme: ThemeId) -> ThemeTokens:
    return _TOKENS[theme]
