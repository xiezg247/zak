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
        root.setSpacing(8)

        header = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("历史会话")
        title.setObjectName("AiSessionTitle")
        header.addWidget(title)
        header.addStretch()
        new_btn = QtWidgets.QPushButton("+ 新会话")
        new_btn.setObjectName("AiToolBtn")
        new_btn.clicked.connect(self._on_new_session)
        header.addWidget(new_btn)
        root.addLayout(header)

        self._list = QtWidgets.QListWidget()
        self._list.setObjectName("AiSessionListWidget")
        self._list.setSpacing(2)
        self._list.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self._list.customContextMenuRequested.connect(self._on_context_menu)
        self._list.itemClicked.connect(self._on_item_clicked)
        self._list.itemDoubleClicked.connect(self._on_item_double_clicked)
        root.addWidget(self._list, stretch=1)

    def refresh(self) -> None:
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
        if current_row >= 0:
            self._list.setCurrentRow(current_row)
        elif selected_row >= 0 and selected_row < self._list.count():
            self._list.setCurrentRow(selected_row)

    def _session_id_at(self, row: int) -> str | None:
        item = self._list.item(row)
        if item is None:
            return None
        session_id = item.data(_SESSION_ID_ROLE)
        return str(session_id) if session_id else None

    def _on_item_clicked(self, item: QtWidgets.QListWidgetItem) -> None:
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
        self._rename_item(item)

    def _on_new_session(self) -> None:
        if self.engine.is_busy():
            QtWidgets.QMessageBox.information(self, "提示", "请等待当前回复完成后再新建会话")
            return
        self.engine.new_session()

    def _on_context_menu(self, pos: QtCore.QPoint) -> None:
        item = self._list.itemAt(pos)
        if item is None:
            return
        session_id = item.data(_SESSION_ID_ROLE)
        if not session_id:
            return
        menu = QtWidgets.QMenu(self)
        rename_action = menu.addAction("重命名")
        delete_action = menu.addAction("删除")
        action = menu.exec(self._list.mapToGlobal(pos))
        if action is rename_action:
            self._rename_item(item)
        elif action is delete_action:
            self._delete_session(str(session_id), item.text().split("\n", 1)[0])

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

    CONTENT_WIDTH = 220
    RAIL_WIDTH = 36

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
        content_layout.setContentsMargins(12, 12, 4, 12)
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
        self._toggle_btn.setFixedSize(28, 28)
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
