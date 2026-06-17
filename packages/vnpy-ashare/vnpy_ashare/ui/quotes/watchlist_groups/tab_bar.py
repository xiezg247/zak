"""自选分组 Tab 条。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.storage.repositories.watchlist_groups import WatchlistGroupRecord
from vnpy_common.ui.theme import theme_manager
from vnpy_common.ui.theme.build_extra import build_watchlist_group_tab_stylesheet

_ALL_GROUP_ID = ""


class WatchlistGroupTabBar(QtWidgets.QWidget):
    """列表上方的自选 / 分组 Tab 切换。"""

    group_selected = QtCore.Signal(str)
    add_requested = QtCore.Signal()
    rename_requested = QtCore.Signal(str)
    delete_requested = QtCore.Signal(str)
    position_cap_requested = QtCore.Signal(str)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("WatchlistGroupTabBar")
        self._layout = QtWidgets.QHBoxLayout(self)
        self._layout.setContentsMargins(8, 4, 8, 2)
        self._layout.setSpacing(4)
        self._button_group = QtWidgets.QButtonGroup(self)
        self._button_group.setExclusive(True)
        theme_manager().bind_stylesheet(self, extra=build_watchlist_group_tab_stylesheet)

    def rebuild(
        self,
        groups: list[WatchlistGroupRecord],
        active_group_id: str | None,
        *,
        max_groups: int,
        tab_labels: dict[str, str] | None = None,
    ) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._button_group.deleteLater()
        self._button_group = QtWidgets.QButtonGroup(self)
        self._button_group.setExclusive(True)

        all_button = self._make_tab("自选", _ALL_GROUP_ID)
        all_button.setChecked(active_group_id is None)
        self._layout.addWidget(all_button)

        separator = QtWidgets.QFrame()
        separator.setObjectName("WatchlistGroupTabSeparator")
        separator.setFrameShape(QtWidgets.QFrame.Shape.VLine)
        separator.setFixedWidth(1)
        self._layout.addWidget(separator)

        for group in groups:
            label = (tab_labels or {}).get(group.id, group.name)
            button = self._make_tab(label, group.id)
            button.setChecked(group.id == active_group_id)
            button.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
            button.customContextMenuRequested.connect(
                lambda pos, group_id=group.id, btn=button: self._show_group_menu(group_id, btn, pos),
            )
            self._layout.addWidget(button)

        add_separator = QtWidgets.QFrame()
        add_separator.setObjectName("WatchlistGroupTabSeparator")
        add_separator.setFrameShape(QtWidgets.QFrame.Shape.VLine)
        add_separator.setFixedWidth(1)
        self._layout.addWidget(add_separator)

        add_button = QtWidgets.QPushButton("+ 新建分组")
        add_button.setObjectName("WatchlistGroupAddButton")
        add_button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        at_limit = len(groups) >= max_groups
        add_button.setEnabled(not at_limit)
        add_button.setToolTip(f"新建自选分组（{len(groups)}/{max_groups}）" if not at_limit else f"已达上限 {max_groups} 个分组")
        add_button.clicked.connect(self.add_requested.emit)
        self._layout.addWidget(add_button)
        self._layout.addStretch(1)

    def _make_tab(self, label: str, group_id: str) -> QtWidgets.QPushButton:
        button = QtWidgets.QPushButton(label)
        button.setObjectName("WatchlistGroupTab")
        button.setCheckable(True)
        self._button_group.addButton(button)
        button.clicked.connect(lambda _checked=False, gid=group_id: self.group_selected.emit(gid))
        return button

    def _show_group_menu(
        self,
        group_id: str,
        button: QtWidgets.QPushButton,
        pos: QtCore.QPoint,
    ) -> None:
        menu = QtWidgets.QMenu(button)
        rename_action = menu.addAction("重命名")
        cap_action = menu.addAction("设置仓位上限")
        delete_action = menu.addAction("删除")
        chosen = menu.exec(button.mapToGlobal(pos))
        if chosen is rename_action:
            self.rename_requested.emit(group_id)
        elif chosen is cap_action:
            self.position_cap_requested.emit(group_id)
        elif chosen is delete_action:
            self.delete_requested.emit(group_id)
