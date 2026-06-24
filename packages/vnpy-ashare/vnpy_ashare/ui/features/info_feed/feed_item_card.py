"""信息流单条卡片。"""

from __future__ import annotations

from datetime import datetime

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.domain.feed.models import FeedItem
from vnpy_ashare.domain.feed.present import feed_item_detail_text, feed_item_meta_text, feed_item_title_text

_TYPE_LABELS = {"video": "视频", "dynamic": "动态", "article": "专栏"}


class FeedItemCard(QtWidgets.QFrame):
    clicked = QtCore.Signal(str)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("FeedItemCard")
        self.setFrameShape(QtWidgets.QFrame.Shape.StyledPanel)
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self._item_id = ""

        self._type_badge = QtWidgets.QLabel(self)
        self._type_badge.setObjectName("FeedItemTypeBadge")
        self._meta_label = QtWidgets.QLabel(self)
        self._meta_label.setObjectName("FeedItemMeta")
        self._title_label = QtWidgets.QLabel(self)
        self._title_label.setObjectName("FeedItemTitle")
        self._title_label.setWordWrap(True)
        self._time_label = QtWidgets.QLabel(self)
        self._time_label.setObjectName("FeedItemTime")
        self._detail_label = QtWidgets.QLabel(self)
        self._detail_label.setObjectName("FeedItemDetail")
        self._detail_label.setWordWrap(True)

        top_row = QtWidgets.QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(6)
        top_row.addWidget(self._type_badge, alignment=QtCore.Qt.AlignmentFlag.AlignVCenter)
        top_row.addWidget(self._meta_label, stretch=1, alignment=QtCore.Qt.AlignmentFlag.AlignVCenter)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)
        layout.addLayout(top_row)
        layout.addWidget(self._title_label)
        layout.addWidget(self._time_label)
        layout.addWidget(self._detail_label)

    def apply(self, item: FeedItem) -> None:
        self._item_id = item.id
        type_label = _TYPE_LABELS.get(item.item_type, item.item_type)
        self._type_badge.setText(type_label)
        _set_widget_property(self._type_badge, "item_type", item.item_type)
        meta_parts = feed_item_meta_text(item).split(" · ")
        if len(meta_parts) > 1:
            self._meta_label.setText(" · ".join(meta_parts[1:]))
        else:
            self._meta_label.setText("")
        self._time_label.setText(_format_when(item.published_at))
        title = feed_item_title_text(item)
        detail = feed_item_detail_text(item)
        self._title_label.setText(title)
        self._detail_label.setText(detail)
        self._detail_label.setVisible(bool(detail))
        tooltip_parts = [item.url]
        if item.summary:
            tooltip_parts.insert(0, item.summary)
        self.setToolTip("\n".join(tooltip_parts))

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() == QtCore.Qt.MouseButton.LeftButton and self._item_id:
            self.clicked.emit(self._item_id)
        super().mouseReleaseEvent(event)


def _format_when(published_at: str) -> str:
    try:
        dt = datetime.fromisoformat(published_at)
    except ValueError:
        return published_at[:16]
    now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()
    if dt.date() == now.date():
        return f"今天 {dt.strftime('%H:%M')}"
    if (now.date() - dt.date()).days == 1:
        return f"昨天 {dt.strftime('%H:%M')}"
    if dt.year == now.year:
        return dt.strftime("%m月%d日 %H:%M")
    return dt.strftime("%Y年%m月%d日 %H:%M")


def _set_widget_property(widget: QtWidgets.QWidget, name: str, value: str) -> None:
    widget.setProperty(name, value)
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)
