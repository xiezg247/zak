"""信息流订阅侧栏。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.domain.feed.models import FeedSubscription
from vnpy_ashare.storage.repositories import feed as feed_repo
from vnpy_ashare.ui.features.info_feed.add_subscription_dialog import AddBilibiliSubscriptionDialog
from vnpy_common.ui.feedback import confirm_action, page_notify

if TYPE_CHECKING:
    from vnpy_ashare.services.feed import FeedService


class SubscriptionPanel(QtWidgets.QWidget):
    selection_changed = QtCore.Signal(str)
    subscriptions_changed = QtCore.Signal()

    def __init__(self, service: FeedService, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._service = service
        self._rows: list[FeedSubscription] = []

        self._list = QtWidgets.QListWidget(self)
        self._list.setObjectName("InfoFeedSubscriptionList")
        self._add_btn = QtWidgets.QPushButton("添加 UP 主", self)
        self._remove_btn = QtWidgets.QPushButton("删除", self)

        actions = QtWidgets.QHBoxLayout()
        actions.addWidget(self._add_btn)
        actions.addWidget(self._remove_btn)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._list, stretch=1)
        layout.addLayout(actions)

        self._add_btn.clicked.connect(self._on_add)
        self._remove_btn.clicked.connect(self._on_remove)
        self._list.currentItemChanged.connect(self._on_current_changed)

    def refresh(self) -> None:
        current_id = self._current_subscription_id()
        self._rows = self._service.list_subscriptions()
        self._list.clear()
        restore_row = 0
        for index, sub in enumerate(self._rows):
            cursor = feed_repo.get_cursor(sub.id)
            status = "启用" if sub.enabled else "停用"
            sync_hint = cursor.get("last_ok_at") or cursor.get("last_error") or "未同步"
            item = QtWidgets.QListWidgetItem(f"{sub.display_name}\n{status} · {sync_hint[:16]}")
            item.setData(QtCore.Qt.ItemDataRole.UserRole, sub.id)
            self._list.addItem(item)
            if sub.id == current_id:
                restore_row = index
        if self._rows:
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
