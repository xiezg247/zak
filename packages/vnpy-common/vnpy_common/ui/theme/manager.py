"""主题切换：持久化、全局 QSS 应用、组件绑定。"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from vnpy.trader.ui import QtCore, QtGui, QtWidgets

from vnpy_common.paths import QSETTINGS_ORG
from vnpy_common.ui.theme.build import build_terminal_stylesheet, stylesheet_for
from vnpy_common.ui.theme.system import resolve_theme_id
from vnpy_common.ui.theme.tokens import (
    DEFAULT_THEME_PREFERENCE,
    THEME_PREFERENCES,
    ThemeId,
    ThemePreference,
    ThemeTokens,
    get_tokens,
)

if TYPE_CHECKING:
    from vnpy.chart import ChartWidget

ExtraStyles = str | Callable[[ThemeTokens], str]
ChartRefreshHandler = Callable[[ThemeTokens, list[Any]], None]

_chart_refresh_handler: ChartRefreshHandler | None = None

_SETTINGS_APP = "ashare_ui"
_SETTINGS_KEY = "ui_theme"


class ThemeManager(QtCore.QObject):
    """全局主题管理（单例）。"""

    theme_changed = QtCore.Signal(str)

    _instance: ThemeManager | None = None

    def __init__(self) -> None:
        super().__init__()
        self._preference: ThemePreference = DEFAULT_THEME_PREFERENCE
        self._bound: list[tuple[QtWidgets.QWidget, ExtraStyles]] = []
        self._callbacks: list[Callable[[ThemeTokens], None]] = []
        self._charts: list[ChartWidget] = []
        self._system_listener_installed = False

    @classmethod
    def instance(cls) -> ThemeManager:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def preference(self) -> ThemePreference:
        return self._preference

    def current(self) -> ThemePreference:
        """用户选择的主题偏好（含 system）。"""
        return self._preference

    def resolved(self) -> ThemeId:
        """当前实际生效的深浅色 id。"""
        return resolve_theme_id(self._preference)

    def tokens(self) -> ThemeTokens:
        return get_tokens(self.resolved())

    def load_saved(self) -> ThemePreference:
        settings = QtCore.QSettings(QSETTINGS_ORG, _SETTINGS_APP)
        raw = settings.value(_SETTINGS_KEY, DEFAULT_THEME_PREFERENCE)
        if raw in THEME_PREFERENCES:
            preference = raw
        else:
            preference = DEFAULT_THEME_PREFERENCE
        self._preference = preference
        return preference

    def set_theme(self, theme: ThemePreference, *, persist: bool = True) -> None:
        if theme not in THEME_PREFERENCES:
            return
        if theme == self._preference:
            return
        self._preference = theme
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

    def register_chart_refresh_handler(self, handler: ChartRefreshHandler) -> None:
        global _chart_refresh_handler
        _chart_refresh_handler = handler

    def bind_stylesheet(self, widget: QtWidgets.QWidget, *, extra: ExtraStyles = "") -> None:
        """绑定 widget：主题切换时重设 setStyleSheet。"""
        self._bound.append((widget, extra))
        self._apply_widget_stylesheet(widget, extra)

    def apply(self) -> None:
        self._ensure_system_listener()
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

    def _ensure_system_listener(self) -> None:
        if self._system_listener_installed:
            return
        hints = QtGui.QGuiApplication.styleHints()
        if not hasattr(hints, "colorSchemeChanged"):
            return
        hints.colorSchemeChanged.connect(self._on_system_color_scheme_changed)
        self._system_listener_installed = True

    def _on_system_color_scheme_changed(self, _scheme: QtCore.Qt.ColorScheme) -> None:
        if self._preference != "system":
            return
        self.apply()
        self.theme_changed.emit("system")

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
        if _chart_refresh_handler is not None:
            _chart_refresh_handler(tokens, self._charts)


def theme_manager() -> ThemeManager:
    return ThemeManager.instance()


__all__ = [
    "ExtraStyles",
    "ThemeManager",
    "build_terminal_stylesheet",
    "stylesheet_for",
    "theme_manager",
]
