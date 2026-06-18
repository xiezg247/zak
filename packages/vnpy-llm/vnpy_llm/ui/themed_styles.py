"""AI 模块主题绑定（基于 vnpy_ashare ThemeManager）。"""

from __future__ import annotations

from vnpy.trader.ui import QtWidgets

from vnpy_common.ui.theme.build_ai import (
    build_ai_floating_stylesheet,
    build_ai_panel_stylesheet,
    build_ai_tools_stylesheet,
    build_ai_trace_stylesheet,
)
from vnpy_common.ui.theme.manager import theme_manager


def bind_ai_panel_style(widget: QtWidgets.QWidget) -> None:
    theme_manager().bind_stylesheet(widget, extra=build_ai_panel_stylesheet)


def bind_ai_floating_style(widget: QtWidgets.QWidget) -> None:
    theme_manager().bind_stylesheet(widget, extra=build_ai_floating_stylesheet)


def bind_ai_tools_dialog_style(widget: QtWidgets.QWidget) -> None:
    def extra(tokens):
        return build_ai_panel_stylesheet(tokens) + build_ai_tools_stylesheet(tokens)

    theme_manager().bind_stylesheet(widget, extra=extra)


def bind_ai_tools_bar_style(widget: QtWidgets.QWidget) -> None:
    theme_manager().bind_stylesheet(widget, extra=build_ai_tools_stylesheet)


def bind_ai_trace_style(widget: QtWidgets.QWidget) -> None:
    theme_manager().bind_stylesheet(widget, extra=build_ai_trace_stylesheet)


def apply_settings_dialog_style(widget: QtWidgets.QWidget) -> None:
    """模态对话框：打开时应用当前主题（不长期绑定）。"""
    from vnpy_common.ui.theme.build import build_terminal_stylesheet
    from vnpy_common.ui.theme.build_extra import build_settings_stylesheet

    manager = theme_manager()
    tokens = manager.tokens()
    widget.setStyleSheet(build_terminal_stylesheet(tokens) + build_settings_stylesheet(tokens))
