"""AI 历史会话列表（全屏侧栏 / Dock 弹窗共用）。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_llm.engine import LlmEngine
from vnpy_llm.store import ChatSession
from vnpy_llm.ui.styles import PANEL_STYLESHEET

_SESSION_ID_ROLE = QtCore.Qt.ItemDataRole.UserRole


def _format_session_subtitle(session: ChatSession) -> str:
    parts: list[str] = []
    if session.message_count > 0:
        parts.append(f"{session.message_count} 条")
    if session.updated_at:
        parts.append(session.updated_at[5:16])
    return " · ".join(parts)


class AiSessionListWidget(QtWidgets.QWidget):
    """可复用的历史会话列表。"""

    session_selected = QtCore.Signal(str)

    def __init__(
        self,
        engine: LlmEngine,
        *,
        close_on_select: bool = False,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.engine = engine
        self._close_on_select = close_on_select
        self._close_parent: QtWidgets.QWidget | None = None
        self._multi_select_mode = False
        self.setObjectName("AiSessionList")
        self.setStyleSheet(PANEL_STYLESHEET)
        self._build_ui()
        self.engine.signals.sessions_changed.connect(self.refresh)
        self.refresh()

    def set_close_parent(self, widget: QtWidgets.QWidget | None) -> None:
        self._close_parent = widget

    def _build_ui(self) -> None:
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)

        title_row = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("历史会话")
        title.setObjectName("AiSessionTitle")
        title_row.addWidget(title)
        title_row.addStretch()
        new_btn = QtWidgets.QPushButton("+ 新会话")
        new_btn.setObjectName("AiToolBtn")
        new_btn.clicked.connect(self._on_new_session)
        title_row.addWidget(new_btn)
        root.addLayout(title_row)

        actions_row = QtWidgets.QHBoxLayout()
        actions_row.setSpacing(6)
        self._multi_btn = QtWidgets.QPushButton("多选")
        self._multi_btn.setObjectName("AiToolBtn")
        self._multi_btn.setCheckable(True)
        self._multi_btn.setToolTip("多选删除会话")
        self._multi_btn.toggled.connect(self._on_multi_select_toggled)
        actions_row.addWidget(self._multi_btn)
        self._del_btn = QtWidgets.QPushButton("删除选中")
        self._del_btn.setObjectName("AiDeleteSessionsBtn")
        self._del_btn.setVisible(False)
        self._del_btn.clicked.connect(self._on_delete_selected)
        actions_row.addWidget(self._del_btn)
        actions_row.addStretch()
        root.addLayout(actions_row)

        self._list = QtWidgets.QListWidget()
        self._list.setObjectName("AiSessionListWidget")
        self._list.setSpacing(2)
        self._list.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.SingleSelection
        )
        self._list.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self._list.customContextMenuRequested.connect(self._on_context_menu)
        self._list.itemClicked.connect(self._on_item_clicked)
        self._list.itemDoubleClicked.connect(self._on_item_double_clicked)
        self._list.itemSelectionChanged.connect(self._on_selection_changed)
        root.addWidget(self._list, stretch=1)

    def _on_multi_select_toggled(self, checked: bool) -> None:
        self._set_multi_select_mode(checked)

    def _set_multi_select_mode(
        self,
        enabled: bool,
        *,
        preselect_item: QtWidgets.QListWidgetItem | None = None,
    ) -> None:
        if self._multi_select_mode == enabled and preselect_item is None:
            return
        self._multi_select_mode = enabled
        if self._multi_btn.isChecked() != enabled:
            self._multi_btn.blockSignals(True)
            self._multi_btn.setChecked(enabled)
            self._multi_btn.blockSignals(False)
        if enabled:
            self._list.setSelectionMode(
                QtWidgets.QAbstractItemView.SelectionMode.MultiSelection
            )
            self._multi_btn.setText("取消")
            self._multi_btn.setToolTip("退出多选模式")
            if preselect_item is not None:
                preselect_item.setSelected(True)
        else:
            self._list.setSelectionMode(
                QtWidgets.QAbstractItemView.SelectionMode.SingleSelection
            )
            self._multi_btn.setText("多选")
            self._multi_btn.setToolTip("多选删除会话")
            self._restore_current_selection()
        self._update_multi_select_ui()

    def _restore_current_selection(self) -> None:
        current_id = self.engine.session_id
        self._list.clearSelection()
        for row in range(self._list.count()):
            item = self._list.item(row)
            if item is None:
                continue
            session_id = item.data(_SESSION_ID_ROLE)
            if session_id and str(session_id) == current_id:
                self._list.setCurrentRow(row)
                break

    def _update_multi_select_ui(self) -> None:
        count = len(self._list.selectedItems())
        if self._multi_select_mode:
            self._del_btn.setVisible(count >= 1)
            self._del_btn.setText(f"删除({count})" if count else "删除选中")
        else:
            self._del_btn.setVisible(False)
            self._del_btn.setText("删除选中")

    def refresh(self) -> None:
        selected_ids = {
            sid for sid, _ in self._selected_sessions()
        } if self._multi_select_mode else set()
        current_id = self.engine.session_id
        selected_row = self._list.currentRow()
        self._list.clear()
        sessions = self.engine.list_sessions()
        current_row = -1
        for index, session in enumerate(sessions):
            subtitle = _format_session_subtitle(session)
            display = session.title if not subtitle else f"{session.title}\n{subtitle}"
            item = QtWidgets.QListWidgetItem(display)
            item.setData(_SESSION_ID_ROLE, session.id)
            item.setToolTip(f"{session.title}\n更新于 {session.updated_at}")
            if subtitle:
                item.setData(QtCore.Qt.ItemDataRole.UserRole + 1, subtitle)
            self._list.addItem(item)
            if session.id == current_id:
                current_row = index
        if self._multi_select_mode:
            for row in range(self._list.count()):
                item = self._list.item(row)
                if item is None:
                    continue
                session_id = item.data(_SESSION_ID_ROLE)
                if session_id and str(session_id) in selected_ids:
                    item.setSelected(True)
            self._update_multi_select_ui()
        elif current_row >= 0:
            self._list.setCurrentRow(current_row)
        elif selected_row >= 0 and selected_row < self._list.count():
            self._list.setCurrentRow(selected_row)

    def _selected_sessions(self) -> list[tuple[str, str]]:
        """返回 [(session_id, title), ...] 当前选中的会话列表。"""
        result: list[tuple[str, str]] = []
        for item in self._list.selectedItems():
            session_id = item.data(_SESSION_ID_ROLE)
            if session_id:
                title = item.text().split("\n", 1)[0]
                result.append((str(session_id), title))
        return result

    def _on_selection_changed(self) -> None:
        self._update_multi_select_ui()

    def _on_delete_selected(self) -> None:
        selected = self._selected_sessions()
        if not selected:
            return
        if self.engine.session_id in {sid for sid, _ in selected}:
            QtWidgets.QMessageBox.warning(
                self, "提示",
                "不能删除当前正在使用的会话，请先切换到其他会话。"
            )
            return
        count = len(selected)
        title_line = f"确定要删除选中的 {count} 个会话及其全部消息吗？"
        if count == 1:
            title_line = f"确定要删除会话「{selected[0][1]}」及其全部消息吗？"
        reply = QtWidgets.QMessageBox.question(
            self,
            "确认删除",
            title_line + ("\n\n" + "\n".join(f"  · {title}" for _, title in selected) if count > 1 else ""),
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
        )
        if reply != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        for session_id, _ in selected:
            self.engine.delete_session(session_id)
        self._set_multi_select_mode(False)

    def _session_id_at(self, row: int) -> str | None:
        item = self._list.item(row)
        if item is None:
            return None
        session_id = item.data(_SESSION_ID_ROLE)
        return str(session_id) if session_id else None

    def _on_item_clicked(self, item: QtWidgets.QListWidgetItem) -> None:
        if self._multi_select_mode:
            return
        if self.engine.is_busy():
            QtWidgets.QMessageBox.information(self, "提示", "请等待当前回复完成后再切换会话")
            return
        session_id = item.data(_SESSION_ID_ROLE)
        if not session_id:
            return
        self.engine.switch_session(str(session_id))
        self.session_selected.emit(str(session_id))
        if self._close_on_select and self._close_parent is not None:
            self._close_parent.close()

    def _on_item_double_clicked(self, item: QtWidgets.QListWidgetItem) -> None:
        if self._multi_select_mode:
            item.setSelected(not item.isSelected())
            return
        self._rename_item(item)

    def _on_new_session(self) -> None:
        if self.engine.is_busy():
            QtWidgets.QMessageBox.information(self, "提示", "请等待当前回复完成后再新建会话")
            return
        self.engine.new_session()

    def _on_context_menu(self, pos: QtCore.QPoint) -> None:
        item = self._list.itemAt(pos)
        selected = self._selected_sessions()
        menu = QtWidgets.QMenu(self)

        if self._multi_select_mode:
            if selected:
                menu.addAction(
                    f"删除选中的 {len(selected)} 个会话",
                    self._on_delete_selected,
                )
            menu.addAction("全选", self._list.selectAll)
            menu.addAction("取消多选", lambda: self._set_multi_select_mode(False))
            menu.exec(self._list.mapToGlobal(pos))
            return

        enter_multi = menu.addAction("多选")
        if item is not None:
            session_id = item.data(_SESSION_ID_ROLE)
            if session_id:
                menu.addSeparator()
                menu.addAction("重命名", lambda: self._rename_item(item))
                menu.addAction(
                    "删除",
                    lambda: self._delete_session(
                        str(session_id), item.text().split("\n", 1)[0]
                    ),
                )
        action = menu.exec(self._list.mapToGlobal(pos))
        if action is enter_multi:
            self._set_multi_select_mode(True, preselect_item=item)

    def _rename_item(self, item: QtWidgets.QListWidgetItem) -> None:
        session_id = item.data(_SESSION_ID_ROLE)
        if not session_id:
            return
        text, ok = QtWidgets.QInputDialog.getText(
            self,
            "重命名会话",
            "会话标题",
            QtWidgets.QLineEdit.EchoMode.Normal,
            item.text().split("\n", 1)[0],
        )
        if ok and text.strip():
            self.engine.rename_session(str(session_id), text.strip())

    def _delete_session(self, session_id: str, title: str) -> None:
        reply = QtWidgets.QMessageBox.question(
            self,
            "确认删除",
            f"删除会话「{title}」及其全部消息？",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
        )
        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            self.engine.delete_session(session_id)


class AiSessionSidebar(QtWidgets.QWidget):
    """全屏页左侧会话栏（可折叠）。"""

    CONTENT_WIDTH = 248
    RAIL_WIDTH = 32

    def __init__(self, engine: LlmEngine, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("AiSessionSidebar")
        self._expanded = True
        self.setFixedWidth(self.CONTENT_WIDTH + self.RAIL_WIDTH)
        self.setStyleSheet(PANEL_STYLESHEET)

        root = QtWidgets.QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._content = QtWidgets.QWidget(self)
        self._content.setFixedWidth(self.CONTENT_WIDTH)
        content_layout = QtWidgets.QVBoxLayout(self._content)
        content_layout.setContentsMargins(10, 10, 6, 10)
        content_layout.setSpacing(0)
        self._list = AiSessionListWidget(engine, parent=self._content)
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
        self._toggle_btn.setText("◀")
        self._toggle_btn.setToolTip("收起历史会话")
        self._toggle_btn.setFixedSize(26, 26)
        self._toggle_btn.clicked.connect(self._toggle_expanded)
        rail_layout.addWidget(self._toggle_btn, alignment=QtCore.Qt.AlignmentFlag.AlignHCenter)
        rail_layout.addStretch()
        root.addWidget(rail)

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
            self._toggle_btn.setToolTip("收起历史会话")
        else:
            self.setFixedWidth(self.RAIL_WIDTH)
            self._toggle_btn.setText("▶")
            self._toggle_btn.setToolTip("展开历史会话")

    def is_expanded(self) -> bool:
        return self._expanded


class AiSessionDialog(QtWidgets.QDialog):
    """Dock 模式历史会话弹窗。"""

    def __init__(
        self,
        engine: LlmEngine,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("历史会话")
        self.setMinimumSize(360, 480)
        self.setStyleSheet(PANEL_STYLESHEET)

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        session_list = AiSessionListWidget(engine, close_on_select=True, parent=self)
        session_list.set_close_parent(self)
        root.addWidget(session_list)


def show_ai_session_dialog(engine: LlmEngine, parent: QtWidgets.QWidget | None = None) -> None:
    dialog = AiSessionDialog(engine, parent)
    dialog.exec()
