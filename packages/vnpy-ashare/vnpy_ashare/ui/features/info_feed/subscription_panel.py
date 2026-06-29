"""信息流订阅侧栏。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.domain.feed.models import FeedSubscription
from vnpy_ashare.ui.features.info_feed.add_subscription_dialog import AddBilibiliSubscriptionDialog
from vnpy_common.ui.feedback import confirm_action, page_notify
from vnpy_common.ui.panel_widgets import content_card, hint_label, section_title

if TYPE_CHECKING:
    from vnpy_ashare.services.feed import FeedService


class SubscriptionPanel(QtWidgets.QWidget):
    selection_changed = QtCore.Signal(str)
    subscriptions_changed = QtCore.Signal()

    def __init__(self, service: FeedService, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("InfoFeedSubscriptionPanel")
        self._service = service
        self._rows: list[FeedSubscription] = []

        title = section_title("订阅源")
        title.setObjectName("InfoFeedSubscriptionTitle")

        self._empty_hint = hint_label("暂无订阅，点击下方添加 UP 主。")
        self._empty_hint.setObjectName("InfoFeedSubscriptionHint")
        self._empty_hint.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        self._list = QtWidgets.QListWidget(self)
        self._list.setObjectName("InfoFeedSubscriptionList")
        self._add_btn = QtWidgets.QPushButton("添加 UP 主", self)
        self._add_btn.setObjectName("ActionButton")
        self._remove_btn = QtWidgets.QPushButton("删除", self)
        self._remove_btn.setObjectName("DangerButton")

        actions = QtWidgets.QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(8)
        actions.addWidget(self._add_btn, stretch=1)
        actions.addWidget(self._remove_btn)

        card_body = QtWidgets.QWidget(self)
        card_layout = QtWidgets.QVBoxLayout(card_body)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(8)
        card_layout.addWidget(title)
        card_layout.addWidget(self._empty_hint)
        card_layout.addWidget(self._list, stretch=1)
        card_layout.addLayout(actions)

        card = content_card(card_body, margins=(12, 10, 12, 10), spacing=0)
        card.setObjectName("InfoFeedSubscriptionCard")

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(card)

        self._add_btn.clicked.connect(self._on_add)
        self._remove_btn.clicked.connect(self._on_remove)
        self._list.currentItemChanged.connect(self._on_current_changed)

    def refresh(self) -> None:
        current_id = self._current_subscription_id()
        self._rows = self._service.list_subscriptions()
        self._list.clear()
        restore_row = 0
        for index, sub in enumerate(self._rows):
            item = QtWidgets.QListWidgetItem(sub.display_name)
            item.setData(QtCore.Qt.ItemDataRole.UserRole, sub.id)
            self._list.addItem(item)
            if sub.id == current_id:
                restore_row = index
        has_rows = bool(self._rows)
        self._empty_hint.setVisible(not has_rows)
        self._list.setVisible(has_rows)
        self._remove_btn.setEnabled(has_rows)
        if has_rows:
            self._list.setCurrentRow(restore_row)

    def _current_subscription_id(self) -> str | None:
        item = self._list.currentItem()
        if item is None:
            return None
        value = item.data(QtCore.Qt.ItemDataRole.UserRole)
        return str(value) if value else None

    def _on_current_changed(self) -> None:
        sub_id = self._current_subscription_id()
        if sub_id:
            self.selection_changed.emit(sub_id)

    def _on_add(self) -> None:
        dialog = AddBilibiliSubscriptionDialog(self._service, self)
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self.refresh()
            self.subscriptions_changed.emit()

    def _on_remove(self) -> None:
        sub_id = self._current_subscription_id()
        if not sub_id:
            page_notify(self, "请先选择订阅", level="warning")
            return
        sub = next((row for row in self._rows if row.id == sub_id), None)
        label = sub.display_name if sub else sub_id
        if not confirm_action(self, "删除订阅", f"确定删除「{label}」？"):
            return
        self._service.remove_subscription(sub_id)
        self.refresh()
        self.subscriptions_changed.emit()
