"""主题切换：持久化、全局 QSS 应用、组件绑定。"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from vnpy.trader.ui import QtCore, QtGui, QtWidgets

from vnpy_ashare.paths import QSETTINGS_ORG
from vnpy_ashare.ui.theme.build import build_terminal_stylesheet, stylesheet_for
from vnpy_ashare.ui.theme.tokens import DEFAULT_THEME, ThemeId, ThemeTokens, get_tokens

if TYPE_CHECKING:
    from vnpy.chart import ChartWidget

ExtraStyles = str | Callable[[ThemeTokens], str]

_SETTINGS_APP = "ashare_ui"
_SETTINGS_KEY = "ui_theme"


class ThemeManager(QtCore.QObject):
    """全局主题管理（单例）。"""

    theme_changed = QtCore.Signal(str)

    _instance: ThemeManager | None = None

    def __init__(self) -> None:
        super().__init__()
        self._theme: ThemeId = DEFAULT_THEME
        self._bound: list[tuple[QtWidgets.QWidget, ExtraStyles]] = []
        self._callbacks: list[Callable[[ThemeTokens], None]] = []
        self._charts: list[ChartWidget] = []

    @classmethod
    def instance(cls) -> ThemeManager:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def current(self) -> ThemeId:
        return self._theme

    def tokens(self) -> ThemeTokens:
        return get_tokens(self._theme)

    def load_saved(self) -> ThemeId:
        settings = QtCore.QSettings(QSETTINGS_ORG, _SETTINGS_APP)
        raw = settings.value(_SETTINGS_KEY, DEFAULT_THEME)
        theme = raw if raw in ("dark", "light") else DEFAULT_THEME
        self._theme = theme
        return theme

    def set_theme(self, theme: ThemeId, *, persist: bool = True) -> None:
        if theme not in ("dark", "light"):
            return
        if theme == self._theme:
            return
        self._theme = theme
        if persist:
            QtCore.QSettings(QSETTINGS_ORG, _SETTINGS_APP).setValue(_SETTINGS_KEY, theme)
        self.apply()
        self.theme_changed.emit(theme)

    def register_callback(self, callback: Callable[[ThemeTokens], None]) -> None:
        self._callbacks.append(callback)

    def register_chart(self, chart: ChartWidget) -> None:
        if chart in self._charts:
            return
        self._charts.append(chart)

    def bind_stylesheet(self, widget: QtWidgets.QWidget, *, extra: ExtraStyles = "") -> None:
        """绑定 widget：主题切换时重设 setStyleSheet。"""
        self._bound.append((widget, extra))
        self._apply_widget_stylesheet(widget, extra)

    def apply(self) -> None:
        tokens = self.tokens()
        qss = build_terminal_stylesheet(tokens)
        app = QtWidgets.QApplication.instance()
        if app is not None:
            self._apply_palette(app, tokens)
            app.setStyleSheet(qss)
        for widget, extra in self._bound:
            self._apply_widget_stylesheet(widget, extra)
        for callback in self._callbacks:
            callback(tokens)
        self._refresh_charts(tokens)

    @staticmethod
    def _apply_palette(app: QtWidgets.QApplication, tokens: ThemeTokens) -> None:
        palette = QtGui.QPalette()
        palette.setColor(QtGui.QPalette.ColorRole.Window, QtGui.QColor(tokens.app_bg))
        palette.setColor(QtGui.QPalette.ColorRole.WindowText, QtGui.QColor(tokens.text_primary))
        palette.setColor(QtGui.QPalette.ColorRole.Base, QtGui.QColor(tokens.input_bg))
        palette.setColor(QtGui.QPalette.ColorRole.AlternateBase, QtGui.QColor(tokens.table_alt))
        palette.setColor(QtGui.QPalette.ColorRole.Text, QtGui.QColor(tokens.text_primary))
        palette.setColor(QtGui.QPalette.ColorRole.Button, QtGui.QColor(tokens.btn_bg))
        palette.setColor(QtGui.QPalette.ColorRole.ButtonText, QtGui.QColor(tokens.btn_text))
        palette.setColor(QtGui.QPalette.ColorRole.Highlight, QtGui.QColor(tokens.table_selected))
        palette.setColor(QtGui.QPalette.ColorRole.HighlightedText, QtGui.QColor(tokens.text_primary))
        palette.setColor(QtGui.QPalette.ColorRole.ToolTipBase, QtGui.QColor(tokens.panel_bg))
        palette.setColor(QtGui.QPalette.ColorRole.ToolTipText, QtGui.QColor(tokens.text_primary))
        palette.setColor(QtGui.QPalette.ColorRole.PlaceholderText, QtGui.QColor(tokens.text_muted))
        app.setPalette(palette)

    def _resolve_extra(self, extra: ExtraStyles, tokens: ThemeTokens) -> str:
        if callable(extra):
            return extra(tokens)
        return extra

    def _apply_widget_stylesheet(self, widget: QtWidgets.QWidget, extra: ExtraStyles) -> None:
        tokens = self.tokens()
        widget.setStyleSheet(build_terminal_stylesheet(tokens) + self._resolve_extra(extra, tokens))

    def _refresh_charts(self, tokens: ThemeTokens) -> None:
        from vnpy_ashare.ui.chart_style import _apply_chart_theme, chart_palette

        palette = chart_palette(tokens)
        for chart in self._charts:
            _apply_chart_theme(chart, palette)


def theme_manager() -> ThemeManager:
    return ThemeManager.instance()


__all__ = [
    "ExtraStyles",
    "ThemeManager",
    "build_terminal_stylesheet",
    "stylesheet_for",
    "theme_manager",
]
