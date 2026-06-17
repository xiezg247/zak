"""查找主窗口实例（duck-type，避免 feature 模块 import main_window 形成环）。"""

from __future__ import annotations

from vnpy.trader.ui import QtWidgets


def _is_ashare_main_window(widget: QtWidgets.QWidget) -> bool:
    return hasattr(widget, "register_floating_overlay") and hasattr(widget, "unregister_floating_overlay") and hasattr(widget, "on_floating_overlay_resized")


def find_ashare_main_window(start: QtWidgets.QWidget) -> QtWidgets.QWidget | None:
    """自 ``start`` 向上遍历父链，再回退到顶层窗口列表。"""
    parent: QtWidgets.QWidget | None = start
    while parent is not None:
        if _is_ashare_main_window(parent):
            return parent
        parent = parent.parentWidget()

    win = start.window()
    if win is not start and _is_ashare_main_window(win):
        return win

    app = QtWidgets.QApplication.instance()
    if app is not None:
        for widget in app.topLevelWidgets():
            if _is_ashare_main_window(widget):
                return widget
    return None
