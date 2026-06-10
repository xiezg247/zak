"""组合终端主样式（base + toolbar + screener）。

``TERMINAL_STYLESHEET`` 唯一定义处；``styles/__init__.py`` 与 ``legacy.apply_legacy_page_style`` 均从此导入。
运行时主题切换见 ``vnpy_common.ui.theme``。
"""

from vnpy_common.ui.theme import stylesheet_for

TERMINAL_STYLESHEET = stylesheet_for("dark")
