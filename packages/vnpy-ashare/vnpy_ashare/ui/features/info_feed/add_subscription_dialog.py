"""添加 B 站 UP 订阅对话框。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.domain.feed.models import FeedSubscriptionConfig
from vnpy_common.ui.feedback import page_notify

if TYPE_CHECKING:
    from vnpy_ashare.services.feed import FeedService


class AddBilibiliSubscriptionDialog(QtWidgets.QDialog):
    def __init__(self, service: FeedService, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._service = service
        self._matches: list[dict[str, str]] = []
        self.setWindowTitle("添加 B 站 UP 主")
        self.resize(480, 360)

        self._keyword_edit = QtWidgets.QLineEdit(self)
        self._keyword_edit.setPlaceholderText("输入 UP 主昵称搜索…")
        self._search_btn = QtWidgets.QPushButton("搜索", self)
        self._mid_edit = QtWidgets.QLineEdit(self)
        self._mid_edit.setPlaceholderText("或直接输入 mid")
        self._result_list = QtWidgets.QListWidget(self)
        self._videos_check = QtWidgets.QCheckBox("采集视频", self)
        self._videos_check.setChecked(True)
        self._dynamics_check = QtWidgets.QCheckBox("采集动态", self)
        self._dynamics_check.setChecked(True)

        search_row = QtWidgets.QHBoxLayout()
        search_row.addWidget(self._keyword_edit, stretch=1)
        search_row.addWidget(self._search_btn)

        form = QtWidgets.QFormLayout()
        form.addRow("搜索", search_row)
        form.addRow("mid", self._mid_edit)
        form.addRow("采集项", self._option_row())

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok | QtWidgets.QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self._result_list, stretch=1)
        layout.addWidget(buttons)

        self._search_btn.clicked.connect(self._on_search)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        self._result_list.itemClicked.connect(self._on_pick_result)

    def _option_row(self) -> QtWidgets.QWidget:
        row = QtWidgets.QWidget(self)
        layout = QtWidgets.QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._videos_check)
        layout.addWidget(self._dynamics_check)
        layout.addStretch()
        return row

    def _on_search(self) -> None:
        keyword = self._keyword_edit.text().strip()
        if not keyword:
            page_notify(self, "请输入搜索关键词", level="warning")
            return
        try:
            self._matches = self._service.search_bilibili_users(keyword)
        except Exception as ex:
            page_notify(self, str(ex), level="error")
            return
        self._result_list.clear()
        for item in self._matches:
            label = f"{item.get('name', '')} (mid={item.get('mid', '')})"
            list_item = QtWidgets.QListWidgetItem(label)
            list_item.setData(QtCore.Qt.ItemDataRole.UserRole, item)
            self._result_list.addItem(list_item)
        if not self._matches:
            page_notify(self, "未找到匹配的 UP 主", level="warning")

    def _on_pick_result(self, item: QtWidgets.QListWidgetItem) -> None:
        data = item.data(QtCore.Qt.ItemDataRole.UserRole) or {}
        self._mid_edit.setText(str(data.get("mid") or ""))

    def _on_accept(self) -> None:
        mid = self._mid_edit.text().strip()
        keyword = "" if mid else self._keyword_edit.text().strip()
        if not mid and not keyword:
            page_notify(self, "请搜索选择 UP 主或填写 mid", level="warning")
            return
        config = FeedSubscriptionConfig(
            videos=self._videos_check.isChecked(),
            dynamics=self._dynamics_check.isChecked(),
        )
        try:
            self._service.add_bilibili_up(mid=mid or None, keyword=keyword or None, config=config)
        except Exception as ex:
            page_notify(self, str(ex), level="error")
            return
        self.accept()
