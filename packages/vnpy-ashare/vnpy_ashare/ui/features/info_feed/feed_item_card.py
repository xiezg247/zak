"""信息流单条卡片。"""

from __future__ import annotations

from datetime import datetime

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.domain.feed.models import FeedItem
from vnpy_ashare.domain.feed.present import feed_item_detail_text, feed_item_meta_text


class FeedItemCard(QtWidgets.QFrame):
    clicked = QtCore.Signal(str)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("FeedItemCard")
        self.setFrameShape(QtWidgets.QFrame.Shape.StyledPanel)
        self._item_id = ""

        self._header_label = QtWidgets.QLabel(self)
        self._header_label.setObjectName("FeedItemHeader")
        self._title_label = QtWidgets.QLabel(self)
        self._title_label.setObjectName("FeedItemTitle")
        self._title_label.setWordWrap(True)
        self._detail_label = QtWidgets.QLabel(self)
        self._detail_label.setObjectName("FeedItemDetail")
        self._detail_label.setWordWrap(True)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)
        layout.addWidget(self._header_label)
        layout.addWidget(self._title_label)
        layout.addWidget(self._detail_label)

    def apply(self, item: FeedItem) -> None:
        self._item_id = item.id
        prefix = "● " if item.is_unread else ""
        when = _format_when(item.published_at)
        self._header_label.setText(f"{prefix}{when} · {feed_item_meta_text(item)}")
        self._title_label.setText(item.title or "（无标题）")
        detail = feed_item_detail_text(item)
        self._detail_label.setText(detail)
        self._detail_label.setVisible(bool(detail))
        tooltip_parts = [item.url]
        if item.summary:
            tooltip_parts.insert(0, item.summary)
        self.setToolTip("\n".join(tooltip_parts))

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        if self._item_id:
            self.clicked.emit(self._item_id)
        super().mouseDoubleClickEvent(event)


def _format_when(published_at: str) -> str:
    try:
        dt = datetime.fromisoformat(published_at)
    except ValueError:
        return published_at[:16]
    return dt.strftime("%m-%d %H:%M")
