"""信息流时间线列表。"""

from __future__ import annotations

import webbrowser
from typing import TYPE_CHECKING

from vnpy.event import Event, EventEngine
from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.ai.context.feed import build_ask_ai_prompt_for_feed_item
from vnpy_ashare.app.events import EVENT_ASK_AI, AskAiRequest
from vnpy_ashare.domain.feed.models import FEED_RECENT_LIMIT, FeedItem
from vnpy_ashare.ui.features.info_feed.feed_item_card import FeedItemCard
from vnpy_common.ui.feedback import page_notify
from vnpy_common.ui.panel_widgets import hint_label, section_title

if TYPE_CHECKING:
    from vnpy_ashare.services.feed import FeedService

_ITEM_ROLE = QtCore.Qt.ItemDataRole.UserRole + 1


class FeedTimelineView(QtWidgets.QWidget):
    def __init__(
        self,
        service: FeedService,
        event_engine: EventEngine | None = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("InfoFeedTimelinePanel")
        self._service = service
        self._event_engine = event_engine
        self._items: list[FeedItem] = []
        self._subscription_id: str | None = None
        self._cards: dict[str, FeedItemCard] = {}

        self._title_label = section_title("时间线")
        self._title_label.setObjectName("InfoFeedTimelineTitle")
        self._count_label = hint_label("")
        self._count_label.setObjectName("InfoFeedTimelineCount")

        header = QtWidgets.QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.addWidget(self._title_label)
        header.addStretch()
        header.addWidget(self._count_label)

        self._empty_hint = hint_label("暂无内容。添加订阅或点击「立即同步」拉取更新。")
        self._empty_hint.setObjectName("InfoFeedEmptyHint")
        self._empty_hint.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        self._list = QtWidgets.QListWidget(self)
        self._list.setObjectName("InfoFeedTimeline")
        self._list.setSpacing(6)
        self._list.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self._list.customContextMenuRequested.connect(self._on_context_menu)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addLayout(header)
        layout.addWidget(self._empty_hint)
        layout.addWidget(self._list, stretch=1)

    def set_subscription_filter(self, subscription_id: str | None) -> None:
        self._subscription_id = subscription_id
        self.refresh()

    def refresh(self) -> None:
        self._items = self._service.list_items(
            limit=FEED_RECENT_LIMIT,
            subscription_id=self._subscription_id,
        )
        self._cards.clear()
        self._list.clear()
        for item in self._items:
            card = FeedItemCard(self._list)
            card.apply(item)
            card.clicked.connect(self._open_item_id)
            row = QtWidgets.QListWidgetItem()
            row.setData(_ITEM_ROLE, item.id)
            card.adjustSize()
            row.setSizeHint(card.sizeHint())
            self._list.addItem(row)
            self._list.setItemWidget(row, card)
            self._cards[item.id] = card

        count = len(self._items)
        self._count_label.setText(f"共 {count} 条")
        has_items = count > 0
        self._empty_hint.setVisible(not has_items)
        self._list.setVisible(has_items)

    def open_current_item(self) -> None:
        item = self._list.currentItem()
        if item is None:
            return
        self._open_item_id(str(item.data(_ITEM_ROLE)))

    def _selected_item(self) -> FeedItem | None:
        widget_item = self._list.currentItem()
        if widget_item is None:
            return None
        item_id = str(widget_item.data(_ITEM_ROLE))
        return next((row for row in self._items if row.id == item_id), None)

    def _on_context_menu(self, pos: QtCore.QPoint) -> None:
        item = self._list.itemAt(pos)
        if item is not None:
            self._list.setCurrentItem(item)
        feed_item = self._selected_item()
        if feed_item is None:
            return
        menu = QtWidgets.QMenu(self)
        open_action = menu.addAction("在浏览器打开")
        ask_action = menu.addAction("问 AI")
        copy_action = menu.addAction("复制链接")
        chosen = menu.exec(self._list.mapToGlobal(pos))
        if chosen is open_action:
            self._open_item_id(feed_item.id)
        elif chosen is ask_action:
            self._ask_ai(feed_item)
        elif chosen is copy_action:
            QtWidgets.QApplication.clipboard().setText(feed_item.url)

    def _ask_ai(self, item: FeedItem) -> None:
        if self._event_engine is None:
            page_notify(self, "AI 引擎未就绪", level="warning")
            return
        self._event_engine.put(
            Event(
                EVENT_ASK_AI,
                AskAiRequest(
                    prompt=build_ask_ai_prompt_for_feed_item(item),
                    source_page="信息流",
                    auto_send=False,
                ),
            )
        )

    def _open_item_id(self, item_id: str) -> None:
        feed_item = next((row for row in self._items if row.id == item_id), None)
        if feed_item is None:
            return
        try:
            webbrowser.open(feed_item.url)
        except Exception as ex:
            page_notify(self, f"无法打开链接：{ex}", level="error")
