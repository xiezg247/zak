"""自选分组管理对话框。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.services.watchlist_service import WatchlistService
from vnpy_ashare.storage.repositories.watchlist_groups import WatchlistGroupRecord
from vnpy_common.ui.feedback import page_notify
from vnpy_common.ui.panel_widgets import center_dialog_on_parent
from vnpy_common.ui.theme import theme_manager
from vnpy_common.ui.theme.build_extra import build_watchlist_group_dialog_stylesheet


class WatchlistGroupManageDialog(QtWidgets.QDialog):
    """新建 / 重命名 / 删除自选分组。"""

    def __init__(
        self,
        service: WatchlistService,
        *,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._service = service
        self._groups: list[WatchlistGroupRecord] = []
        self.setObjectName("WatchlistGroupDialog")
        self.setWindowTitle("管理自选分组")
        self.setMinimumSize(420, 360)
        self.resize(460, 400)
        center_dialog_on_parent(self, parent)

        title = QtWidgets.QLabel("自选分组")
        title.setObjectName("WatchlistGroupDialogTitle")

        hint = QtWidgets.QLabel("分组用于筛选自选列表；同一只标的可加入多个分组。")
        hint.setObjectName("SettingsHint")
        hint.setWordWrap(True)

        self._meta_label = QtWidgets.QLabel("")
        self._meta_label.setObjectName("SettingsMeta")

        self._list = QtWidgets.QListWidget()
        self._list.setObjectName("WatchlistGroupList")
        self._list.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self._list.setAlternatingRowColors(True)
        self._list.setMinimumHeight(220)

        self._add_button = QtWidgets.QPushButton("新建")
        self._add_button.setObjectName("ActionButton")
        self._rename_button = QtWidgets.QPushButton("重命名")
        self._rename_button.setObjectName("SecondaryButton")
        self._delete_button = QtWidgets.QPushButton("删除")
        self._delete_button.setObjectName("SecondaryButton")

        action_row = QtWidgets.QHBoxLayout()
        action_row.setSpacing(10)
        action_row.addWidget(self._add_button)
        action_row.addWidget(self._rename_button)
        action_row.addWidget(self._delete_button)
        action_row.addStretch(1)

        self._close_button = QtWidgets.QPushButton("关闭")
        self._close_button.setObjectName("SecondaryButton")
        self._close_button.setMinimumWidth(72)

        footer = QtWidgets.QHBoxLayout()
        footer.addStretch(1)
        footer.addWidget(self._close_button)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 12)
        layout.setSpacing(12)
        layout.addWidget(title)
        layout.addWidget(hint)
        layout.addWidget(self._meta_label)
        layout.addWidget(self._list, stretch=1)
        layout.addLayout(action_row)
        layout.addLayout(footer)

        self._add_button.clicked.connect(self._on_add)
        self._rename_button.clicked.connect(self._on_rename)
        self._delete_button.clicked.connect(self._on_delete)
        self._close_button.clicked.connect(self.accept)
        self._list.itemSelectionChanged.connect(self._sync_buttons)
        self._list.itemDoubleClicked.connect(self._on_item_double_clicked)

        theme_manager().bind_stylesheet(self, extra=build_watchlist_group_dialog_stylesheet)
        self.reload()

    def reload(self) -> None:
        self._groups = self._service.list_groups()
        self._list.clear()
        if not self._groups:
            placeholder = QtWidgets.QListWidgetItem("暂无分组，点击「新建」创建第一个分组")
            placeholder.setFlags(QtCore.Qt.ItemFlag.NoItemFlags)
            placeholder.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignHCenter | QtCore.Qt.AlignmentFlag.AlignVCenter)
            self._list.addItem(placeholder)
        else:
            for group in self._groups:
                member_count = len(self._service.group_member_keys(group.id))
                label = group.name if member_count <= 0 else f"{group.name}  ·  {member_count} 只"
                item = QtWidgets.QListWidgetItem(label)
                item.setData(QtCore.Qt.ItemDataRole.UserRole, group.id)
                self._list.addItem(item)
        self._meta_label.setText(f"共 {len(self._groups)} / {self._service.max_groups} 个分组")
        self._sync_buttons()

    def _selected_group(self) -> WatchlistGroupRecord | None:
        item = self._list.currentItem()
        if item is None:
            return None
        group_id = str(item.data(QtCore.Qt.ItemDataRole.UserRole) or "")
        if not group_id:
            return None
        for group in self._groups:
            if group.id == group_id:
                return group
        return None

    def _sync_buttons(self) -> None:
        has_selection = self._selected_group() is not None
        self._rename_button.setEnabled(has_selection)
        self._delete_button.setEnabled(has_selection)
        self._add_button.setEnabled(len(self._groups) < self._service.max_groups)

    def _on_item_double_clicked(self, item: QtWidgets.QListWidgetItem) -> None:
        if not str(item.data(QtCore.Qt.ItemDataRole.UserRole) or ""):
            return
        self._on_rename()

    def _prompt_name(self, *, title: str, label: str, initial: str = "") -> str | None:
        text, ok = QtWidgets.QInputDialog.getText(self, title, label, text=initial)
        if not ok:
            return None
        normalized = str(text or "").strip()
        return normalized or None

    def _on_add(self) -> None:
        name = self._prompt_name(title="新建分组", label="分组名称：")
        if name is None:
            return
        group_id = self._service.create_group(name)
        if group_id is None:
            page_notify(self, "无法创建分组（名称重复或已达上限）", level="warning")
            return
        self.reload()
        for row in range(self._list.count()):
            item = self._list.item(row)
            if item is not None and str(item.data(QtCore.Qt.ItemDataRole.UserRole) or "") == group_id:
                self._list.setCurrentItem(item)
                break

    def _on_rename(self) -> None:
        group = self._selected_group()
        if group is None:
            return
        name = self._prompt_name(title="重命名分组", label="分组名称：", initial=group.name)
        if name is None:
            return
        if not self._service.rename_group(group.id, name):
            page_notify(self, "重命名失败（名称可能重复）", level="warning")
            return
        self.reload()

    def _on_delete(self) -> None:
        group = self._selected_group()
        if group is None:
            return
        answer = QtWidgets.QMessageBox.question(
            self,
            "删除分组",
            f"确定删除分组「{group.name}」？\n标的仍保留在自选池与其它分组中。",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No,
        )
        if answer != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        if not self._service.delete_group(group.id):
            page_notify(self, "删除分组失败", level="warning")
            return
        self.reload()
