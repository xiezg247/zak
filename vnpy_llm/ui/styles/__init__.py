"""AI 面板 QSS（按域拆分，对外保持原 import 路径）。"""

from vnpy_llm.ui.styles.floating import FLOATING_CHAT_INNER_STYLESHEET, FLOATING_CHAT_STYLESHEET
from vnpy_llm.ui.styles.panel import PANEL_STYLESHEET
from vnpy_llm.ui.styles.tools import TOOLS_WIDGET_STYLESHEET
from vnpy_llm.ui.styles.trace import INLINE_TRACE_STYLESHEET

__all__ = [
    "FLOATING_CHAT_INNER_STYLESHEET",
    "FLOATING_CHAT_STYLESHEET",
    "INLINE_TRACE_STYLESHEET",
    "PANEL_STYLESHEET",
    "TOOLS_WIDGET_STYLESHEET",
]
