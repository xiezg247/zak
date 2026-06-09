"""选股页历史运行侧栏。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtGui, QtWidgets

from vnpy_ashare.screener.run_store import (
    delete_run,
    is_auto_run,
    is_run_unread,
    list_runs,
)
from vnpy_ashare.ui.styles import TERMINAL_STYLESHEET

_RUN_ID_ROLE = QtCore.Qt.ItemDataRole.UserRole
_RUN_CONDITION_ROLE = QtCore.Qt.ItemDataRole.UserRole + 1

_FILTER_ALL = "all"
_FILTER_MANUAL = "manual"
_FILTER_AUTO = "auto"

_TRIGGER_TAGS = {
    "scheduled_intraday": "[盘中]",
    "scheduled_post_close": "[盘后]",
}


def _run_filter_label(record) -> str:
    trigger = str(record.config.get("trigger", ""))
    tag = _TRIGGER_TAGS.get(trigger, "")
    title = record.condition
    if tag and not title.startswith("["):
        title = f"{tag} {title}"
    return title


class ScreenerRunListWidget(QtWidgets.QWidget):
    """可复用的选股历史列表。"""

    run_selected = QtCore.Signal(str)
    copy_run_id_requested = QtCore.Signal(str, str)
    ask_ai_requested = QtCore.Signal(str, str)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ScreenerRunList")
        self.setStyleSheet(TERMINAL_STYLESHEET)
        self._filter = _FILTER_ALL
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        title = QtWidgets.QLabel("历史运行")
        title.setObjectName("AiSessionTitle")
        root.addWidget(title)

        self._filter_tabs = QtWidgets.QTabBar()
        self._filter_tabs.setObjectName("ScreenerRunFilterTabs")
        self._filter_tabs.addTab("全部")
        self._filter_tabs.addTab("手动")
        self._filter_tabs.addTab("自动")
        self._filter_tabs.currentChanged.connect(self._on_filter_changed)
        root.addWidget(self._filter_tabs)

        self._list = QtWidgets.QListWidget()
        self._list.setObjectName("AiSessionListWidget")
        self._list.setSpacing(2)
        self._list.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self._list.customContextMenuRequested.connect(self._on_context_menu)
        self._list.itemClicked.connect(self._on_item_clicked)
        self._list.itemSelectionChanged.connect(self._update_action_buttons)
        root.addWidget(self._list, stretch=1)

        action_row = QtWidgets.QHBoxLayout()
        action_row.setSpacing(6)
        self._copy_btn = QtWidgets.QPushButton("复制 ID")
        self._copy_btn.setObjectName("SecondaryButton")
        self._copy_btn.setToolTip("复制 run_id 到剪贴板")
        self._copy_btn.clicked.connect(self._copy_selected_run_id)
        self._ask_ai_btn = QtWidgets.QPushButton("问 AI")
        self._ask_ai_btn.setObjectName("SecondaryButton")
        self._ask_ai_btn.setToolTip("打开 AI 并预填解读请求")
        self._ask_ai_btn.clicked.connect(self._ask_ai_for_selected)
        action_row.addWidget(self._copy_btn)
        action_row.addWidget(self._ask_ai_btn)
        root.addLayout(action_row)
        self._update_action_buttons()

    def _on_filter_changed(self, index: int) -> None:
        filters = [_FILTER_ALL, _FILTER_MANUAL, _FILTER_AUTO]
        self._filter = filters[index] if 0 <= index < len(filters) else _FILTER_ALL
        self.refresh()

    def _matches_filter(self, record) -> bool:
        if self._filter == _FILTER_ALL:
            return True
        auto = is_auto_run(record.config)
        if self._filter == _FILTER_AUTO:
            return auto
        return not auto

    def _selected_item(self) -> QtWidgets.QListWidgetItem | None:
        return self._list.currentItem()

    def _selected_run(self) -> tuple[str, str] | None:
        item = self._selected_item()
        if item is None:
            return None
        run_id = item.data(_RUN_ID_ROLE)
        if not run_id:
            return None
        condition = str(item.data(_RUN_CONDITION_ROLE) or item.text().split("\n", 1)[0])
        return str(run_id), condition

    def _update_action_buttons(self) -> None:
        enabled = self._selected_run() is not None
        self._copy_btn.setEnabled(enabled)
        self._ask_ai_btn.setEnabled(enabled)

    def refresh(self) -> None:
        selected_id = None
        current = self._selected_run()
        if current is not None:
            selected_id = current[0]
        self._list.clear()
        restore_row = -1
        for record in list_runs(limit=30):
            if not self._matches_filter(record):
                continue
            title = _run_filter_label(record)
            subtitle = f"{record.row_count} 条 · {record.created_at[5:16]}"
            display = f"{title}\n{subtitle}"
            item = QtWidgets.QListWidgetItem(display)
            item.setData(_RUN_ID_ROLE, record.id)
            item.setData(_RUN_CONDITION_ROLE, record.condition)
            if is_run_unread(record.config):
                font = item.font()
                font.setBold(True)
                item.setFont(font)
                item.setForeground(QtGui.QColor("#7dd3fc"))
            reason = record.config.get("reason_summary") or record.config.get("trigger", "")
            item.setToolTip(
                f"{title}\n"
                f"run_id: {record.id}\n"
                f"来源 {record.source} · 扫描 {record.total_scanned} · {record.created_at}\n"
                f"{reason}"
            )
            self._list.addItem(item)
            if selected_id and record.id == selected_id:
                restore_row = self._list.count() - 1
        if restore_row >= 0:
            self._list.setCurrentRow(restore_row)
        elif self._list.count() > 0:
            self._list.setCurrentRow(0)
        self._update_action_buttons()

    def _on_item_clicked(self, item: QtWidgets.QListWidgetItem) -> None:
        run_id = item.data(_RUN_ID_ROLE)
        if run_id:
            self.run_selected.emit(str(run_id))

    def _copy_selected_run_id(self) -> None:
        selected = self._selected_run()
        if selected is None:
            return
        run_id, condition = selected
        QtWidgets.QApplication.clipboard().setText(run_id)
        self.copy_run_id_requested.emit(run_id, condition)

    def _ask_ai_for_selected(self) -> None:
        selected = self._selected_run()
        if selected is None:
            return
        run_id, condition = selected
        self.ask_ai_requested.emit(run_id, condition)

    def _on_context_menu(self, pos: QtCore.QPoint) -> None:
        item = self._list.itemAt(pos)
        if item is None:
            return
        run_id = item.data(_RUN_ID_ROLE)
        if not run_id:
            return
        condition = str(item.data(_RUN_CONDITION_ROLE) or item.text().split("\n", 1)[0])
        self._list.setCurrentItem(item)
        menu = QtWidgets.QMenu(self)
        copy_action = menu.addAction("复制 run_id")
        ask_action = menu.addAction("发给 AI 解读")
        menu.addSeparator()
        delete_action = menu.addAction("删除")
        action = menu.exec(self._list.mapToGlobal(pos))
        if action is copy_action:
            QtWidgets.QApplication.clipboard().setText(str(run_id))
            self.copy_run_id_requested.emit(str(run_id), condition)
        elif action is ask_action:
            self.ask_ai_requested.emit(str(run_id), condition)
        elif action is delete_action:
            title = item.text().split("\n", 1)[0]
            reply = QtWidgets.QMessageBox.question(
                self,
                "确认删除",
                f"删除历史运行「{title}」？",
                QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
            )
            if reply == QtWidgets.QMessageBox.StandardButton.Yes:
                delete_run(str(run_id))
                self.refresh()


class ScreenerRunSidebar(QtWidgets.QWidget):
    """选股页左侧历史栏（可折叠）。"""

    run_selected = QtCore.Signal(str)
    copy_run_id_requested = QtCore.Signal(str, str)
    ask_ai_requested = QtCore.Signal(str, str)

    CONTENT_WIDTH = 200
    RAIL_WIDTH = 36

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("AiSessionSidebar")
        self._expanded = False
        self.setFixedWidth(self.RAIL_WIDTH)
        self.setStyleSheet(TERMINAL_STYLESHEET)

        root = QtWidgets.QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._content = QtWidgets.QWidget(self)
        self._content.setFixedWidth(self.CONTENT_WIDTH)
        self._content.setVisible(False)
        content_layout = QtWidgets.QVBoxLayout(self._content)
        content_layout.setContentsMargins(12, 12, 4, 12)
        content_layout.setSpacing(0)
        self._list = ScreenerRunListWidget(parent=self._content)
        self._list.run_selected.connect(self.run_selected.emit)
        self._list.copy_run_id_requested.connect(self.copy_run_id_requested.emit)
        self._list.ask_ai_requested.connect(self.ask_ai_requested.emit)
        content_layout.addWidget(self._list)
        root.addWidget(self._content)

        rail = QtWidgets.QWidget(self)
        rail.setObjectName("AiSessionRail")
        rail.setFixedWidth(self.RAIL_WIDTH)
        rail_layout = QtWidgets.QVBoxLayout(rail)
        rail_layout.setContentsMargins(0, 12, 0, 12)
        rail_layout.addStretch()
        self._toggle_btn = QtWidgets.QToolButton()
        self._toggle_btn.setObjectName("AiSessionToggle")
        self._toggle_btn.setText("▶")
        self._toggle_btn.setToolTip("展开历史运行")
        self._toggle_btn.setFixedSize(28, 28)
        self._toggle_btn.clicked.connect(self._toggle_expanded)
        rail_layout.addWidget(self._toggle_btn, alignment=QtCore.Qt.AlignmentFlag.AlignHCenter)
        rail_layout.addStretch()
        root.addWidget(rail)

    def refresh(self) -> None:
        self._list.refresh()

    def _toggle_expanded(self) -> None:
        self.set_expanded(not self._expanded)

    def set_expanded(self, expanded: bool) -> None:
        if self._expanded == expanded:
            return
        self._expanded = expanded
        self._content.setVisible(expanded)
        if expanded:
            self.setFixedWidth(self.CONTENT_WIDTH + self.RAIL_WIDTH)
            self._toggle_btn.setText("◀")
            self._toggle_btn.setToolTip("收起历史运行")
        else:
            self.setFixedWidth(self.RAIL_WIDTH)
            self._toggle_btn.setText("▶")
            self._toggle_btn.setToolTip("展开历史运行")
