"""自选页池子关系上下文条。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtGui, QtWidgets

from vnpy_ashare.config.preferences.watchlist_signal import load_signal_panel_symbols
from vnpy_ashare.ui.quotes._host_widget import as_qwidget
from vnpy_ashare.ui.quotes.features.watchlist.pool_context_summary import format_pool_context_summary
from vnpy_ashare.ui.quotes.page.strategy_bridge import navigate_to_strategy_monitor
from vnpy_ashare.ui.quotes.watchlist.host import WatchlistHost

__all__ = [
    "WatchlistPoolContextBar",
    "format_pool_context_summary",
]


class WatchlistPoolContextBar(QtWidgets.QWidget):
    """主表上方一行：三层池用量摘要，点击可聚焦对应区域。"""

    def __init__(self, page: WatchlistHost, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._page = page
        self.setObjectName("WatchlistPoolContextBar")

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(8, 2, 8, 2)
        layout.setSpacing(0)

        self._label = QtWidgets.QLabel("", self)
        self._label.setObjectName("WatchlistPoolContextLabel")
        self._label.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
        self._label.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self._label.setToolTip("三层池：自选（总名单）→ 信号（当日监控）→ 持仓（已登记）。点击各段可切换视图；右键表行可回测、排序、下载与 AI 分析。")
        layout.addWidget(self._label, stretch=1)

        self._segments: list[tuple[str, str]] = []
        self._label.installEventFilter(self)

    def refresh(self) -> None:
        page = self._page
        pool_count = len(page.watchlist_pool_stocks or page.all_stocks)
        signal_panel = getattr(page, "signal_panel", None)
        signal_count = len(signal_panel.symbols) if signal_panel is not None else len(load_signal_panel_symbols())
        position_service = page._get_position_service()
        position_count = position_service.count() if position_service is not None else 0
        text = format_pool_context_summary(
            pool_count=pool_count,
            signal_count=signal_count,
            position_count=position_count,
        )
        self._segments = self._build_segments(text)
        if getattr(page._signals, "is_refreshing", False):
            text += " · 信号刷新中"
        if getattr(page._positions, "is_refreshing", False):
            text += " · 持仓刷新中"
        self._label.setText(text)

    @staticmethod
    def _build_segments(text: str) -> list[tuple[str, str]]:
        parts = [part.strip() for part in text.split("·")]
        keys = ("pool", "signal", "position")
        return list(zip(keys, parts, strict=True))

    def eventFilter(self, watched: QtCore.QObject, event: QtCore.QEvent) -> bool:  # noqa: N802
        if watched is self._label and event.type() == QtCore.QEvent.Type.MouseButtonRelease:
            mouse = event
            if isinstance(mouse, QtGui.QMouseEvent) and mouse.button() == QtCore.Qt.MouseButton.LeftButton:
                self._on_label_clicked(mouse.pos())
                return True
        return super().eventFilter(watched, event)

    def _on_label_clicked(self, pos) -> None:
        if not self._segments:
            return
        metrics = self._label.fontMetrics()
        x = pos.x()
        cursor_x = 0
        for key, segment in self._segments:
            width = metrics.horizontalAdvance(segment) + metrics.horizontalAdvance(" · ")
            if x <= cursor_x + width:
                self._focus_segment(key)
                return
            cursor_x += width

    def _focus_segment(self, key: str) -> None:
        page = self._page
        if key == "pool":
            groups = page._watchlist_groups
            if groups is not None:
                groups.select_all_tab()
            return
        if key == "signal":
            navigate_to_strategy_monitor(as_qwidget(page))
            monitor = getattr(page, "_strategy_monitor_feature", None)
            if monitor is not None:
                monitor.apply_layout_preset("intraday")
            return
        if key == "position":
            navigate_to_strategy_monitor(as_qwidget(page))
            monitor = getattr(page, "_strategy_monitor_feature", None)
            if monitor is not None:
                monitor.apply_position_focus()
            return
