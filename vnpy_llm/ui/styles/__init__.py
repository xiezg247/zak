"""AI 面板 QSS（按域拆分，对外保持原 import 路径）。

子模块：quick_action / chat_bubble / panel / floating / tools / trace。
``PANEL_STYLESHEET`` 在 panel.py 内组合 bubble + quick_action；floating 复用 quick_action。
"""

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
