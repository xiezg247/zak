"""自选页池子关系上下文条。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vnpy.trader.ui import QtCore, QtGui, QtWidgets

from vnpy_ashare.config.preferences.watchlist_signal import SIGNAL_PANEL_MAX_SYMBOLS
from vnpy_ashare.services.watchlist import WATCHLIST_MAX_ITEMS
from vnpy_ashare.services.watchlist_short_term import (
    SHORT_TERM_OBSERVATION_GROUP_NAME,
    find_short_term_observation_group_id,
)
from vnpy_ashare.storage.repositories.positions import POSITION_MAX_ITEMS, position_item_count
from vnpy_ashare.ui.quotes.watchlist_signals.splitter import apply_center_splitter_sizes

if TYPE_CHECKING:
    from vnpy_ashare.ui.quotes.page.quotes_page import QuotesPage

SHORT_TERM_OBSERVATION_MAX = 5


def format_pool_context_summary(
    *,
    pool_count: int,
    observation_count: int,
    signal_count: int,
    position_count: int,
) -> str:
    return (
        f"自选 {pool_count}/{WATCHLIST_MAX_ITEMS}"
        f" · 观察组 {observation_count}/{SHORT_TERM_OBSERVATION_MAX}"
        f" · 信号 {signal_count}/{SIGNAL_PANEL_MAX_SYMBOLS}"
        f" · 持仓 {position_count}/{POSITION_MAX_ITEMS}"
    )


class WatchlistPoolContextBar(QtWidgets.QWidget):
    """主表上方一行：四层池子用量摘要，点击可聚焦对应区域。"""

    def __init__(self, page: QuotesPage, parent: QtWidgets.QWidget | None = None) -> None:
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
        self._label.setToolTip("点击各段可展开对应区域（观察组段切换至「短线观察」分组）")
        layout.addWidget(self._label, stretch=1)

        self._segments: list[tuple[str, str]] = []
        self._label.installEventFilter(self)

    def refresh(self) -> None:
        page = self._page
        pool_count = len(page.watchlist_pool_stocks or page.all_stocks)
        observation_count = self._observation_count()
        signal_panel = getattr(page, "signal_panel", None)
        signal_count = len(signal_panel.symbols) if signal_panel is not None else 0
        position_count = position_item_count()
        text = format_pool_context_summary(
            pool_count=pool_count,
            observation_count=observation_count,
            signal_count=signal_count,
            position_count=position_count,
        )
        self._segments = self._build_segments(text)
        self._label.setText(text)

    def _observation_count(self) -> int:
        service = self._page._get_watchlist_service()
        if service is None:
            return 0
        group_id = find_short_term_observation_group_id(service)
        if group_id is None:
            return 0
        return len(service.group_member_keys(group_id))

    @staticmethod
    def _build_segments(text: str) -> list[tuple[str, str]]:
        parts = [part.strip() for part in text.split("·")]
        keys = ("pool", "observation", "signal", "position")
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
        if key == "observation":
            groups = page._watchlist_groups
            if groups is not None:
                groups.select_observation_group_tab()
            return
        if key == "signal":
            panel = getattr(page, "signal_panel", None)
            if panel is not None:
                panel.set_expanded(True)
                apply_center_splitter_sizes(page)
            return
        if key == "position":
            panel = getattr(page, "position_panel", None)
            if panel is not None:
                panel.set_expanded(True)
                apply_center_splitter_sizes(page)
