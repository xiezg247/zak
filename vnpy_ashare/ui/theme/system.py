"""读取操作系统浅色 / 深色外观。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtGui, QtWidgets

from vnpy_ashare.ui.theme.tokens import DEFAULT_THEME, ThemeId, ThemePreference


def detect_system_theme_id() -> ThemeId:
    """根据当前系统外观推断应使用的主题 id。"""
    hints = QtGui.QGuiApplication.styleHints()
    if hasattr(hints, "colorScheme"):
        scheme = hints.colorScheme()
        if scheme == QtCore.Qt.ColorScheme.Dark:
            return "dark"
        if scheme == QtCore.Qt.ColorScheme.Light:
            return "light"

    app = QtWidgets.QApplication.instance()
    if app is not None:
        window = app.style().standardPalette().color(QtGui.QPalette.ColorRole.Window)
        return "light" if window.lightness() > 128 else "dark"
    return DEFAULT_THEME


def resolve_theme_id(preference: ThemePreference) -> ThemeId:
    if preference == "dark":
        return "dark"
    return detect_system_theme_id()
