"""券商终端风格 QSS（按域拆分，对外保持原 import 路径）。"""

from vnpy_ashare.ui.styles.colors import (
    ACCENT_COLOR,
    FALL_COLOR,
    FLAT_COLOR,
    HEADER_BG,
    NAV_MUTED_COLOR,
    PANEL_BG,
    RISE_COLOR,
)
from vnpy_ashare.ui.styles.compose import TERMINAL_STYLESHEET
from vnpy_ashare.ui.styles.legacy import (
    LEGACY_PAGE_STYLESHEET,
    apply_legacy_page_style,
    apply_settings_combo_style,
    apply_toolbar_combo_style,
    style_legacy_form_inputs,
    style_legacy_push_buttons,
)
from vnpy_ashare.ui.styles.scheduler import SCHEDULER_PAGE_STYLESHEET, SCHEDULER_TABLE_STYLESHEET
from vnpy_ashare.ui.styles.screener import SCREENER_STYLESHEET
from vnpy_ashare.ui.styles.settings import SETTINGS_DIALOG_STYLESHEET
from vnpy_ashare.ui.styles.toolbar import TOOLBAR_COMBO_STYLESHEET

__all__ = [
    "ACCENT_COLOR",
    "FALL_COLOR",
    "FLAT_COLOR",
    "HEADER_BG",
    "LEGACY_PAGE_STYLESHEET",
    "NAV_MUTED_COLOR",
    "PANEL_BG",
    "RISE_COLOR",
    "SCHEDULER_PAGE_STYLESHEET",
    "SCHEDULER_TABLE_STYLESHEET",
    "SCREENER_STYLESHEET",
    "SETTINGS_DIALOG_STYLESHEET",
    "TERMINAL_STYLESHEET",
    "TOOLBAR_COMBO_STYLESHEET",
    "apply_legacy_page_style",
    "apply_settings_combo_style",
    "apply_toolbar_combo_style",
    "style_legacy_form_inputs",
    "style_legacy_push_buttons",
]
