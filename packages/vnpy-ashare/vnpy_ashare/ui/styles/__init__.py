"""券商终端风格 QSS（按域拆分，对外保持原 import 路径）。

子模块按页面/控件域拆分 QSS 字符串；组合逻辑见 ``compose.TERMINAL_STYLESHEET``。
业务代码继续 ``from vnpy_ashare.ui.styles import TERMINAL_STYLESHEET``，勿引用子模块。
"""

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
from vnpy_ashare.ui.styles.scheduler import SCHEDULER_PAGE_STYLESHEET, SCHEDULER_TABLE_STYLESHEET
from vnpy_ashare.ui.styles.settings import SETTINGS_DIALOG_STYLESHEET
from vnpy_ashare.ui.styles.toolbar import TOOLBAR_COMBO_STYLESHEET
from vnpy_ashare.ui.styles.vnpy_page import (
    VNPY_PAGE_STYLESHEET,
    apply_settings_combo_style,
    apply_toolbar_combo_style,
    apply_vnpy_page_style,
    style_vnpy_form_inputs,
    style_vnpy_push_buttons,
)

__all__ = [
    "ACCENT_COLOR",
    "FALL_COLOR",
    "FLAT_COLOR",
    "HEADER_BG",
    "VNPY_PAGE_STYLESHEET",
    "NAV_MUTED_COLOR",
    "PANEL_BG",
    "RISE_COLOR",
    "SCHEDULER_PAGE_STYLESHEET",
    "SCHEDULER_TABLE_STYLESHEET",
    "SETTINGS_DIALOG_STYLESHEET",
    "TERMINAL_STYLESHEET",
    "TOOLBAR_COMBO_STYLESHEET",
    "apply_vnpy_page_style",
    "apply_settings_combo_style",
    "apply_toolbar_combo_style",
    "style_vnpy_form_inputs",
    "style_vnpy_push_buttons",
]
