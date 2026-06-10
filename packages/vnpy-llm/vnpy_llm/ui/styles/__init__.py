"""AI 面板 QSS（按域拆分，对外保持原 import 路径）。

子模块保留以兼容旧引用；``PANEL_STYLESHEET`` 等常量由主题 token 生成。
"""

from vnpy_common.ui.theme.build_ai import (
    INLINE_TRACE_STYLESHEET,
    PANEL_STYLESHEET,
    TOOLS_WIDGET_STYLESHEET,
    build_ai_floating_stylesheet,
)
from vnpy_common.ui.theme.tokens import DARK_TOKENS

FLOATING_CHAT_STYLESHEET = build_ai_floating_stylesheet(DARK_TOKENS)
FLOATING_CHAT_INNER_STYLESHEET = ""

__all__ = [
    "FLOATING_CHAT_INNER_STYLESHEET",
    "FLOATING_CHAT_STYLESHEET",
    "INLINE_TRACE_STYLESHEET",
    "PANEL_STYLESHEET",
    "TOOLS_WIDGET_STYLESHEET",
]
