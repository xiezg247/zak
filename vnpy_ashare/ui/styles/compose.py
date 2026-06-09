"""组合终端主样式（base + toolbar + screener）。"""

from vnpy_ashare.ui.styles.screener import SCREENER_STYLESHEET
from vnpy_ashare.ui.styles.terminal_base import TERMINAL_STYLESHEET as _TERMINAL_BASE
from vnpy_ashare.ui.styles.toolbar import TOOLBAR_COMBO_STYLESHEET

TERMINAL_STYLESHEET = _TERMINAL_BASE + TOOLBAR_COMBO_STYLESHEET + SCREENER_STYLESHEET
