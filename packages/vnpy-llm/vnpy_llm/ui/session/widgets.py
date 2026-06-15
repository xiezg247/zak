"""AI 历史会话列表（全屏侧栏 / Dock 弹窗共用）。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtGui, QtWidgets

from vnpy_common.ui.feedback import confirm_action, page_notify
from vnpy_llm.app.engine import LlmEngine
from vnpy_llm.chat.store import ChatSession
from vnpy_llm.ui.themed_styles import bind_ai_panel_style

_SESSION_ID_ROLE = QtCore.Qt.ItemDataRole.UserRole


def _format_session_subtitle(session: ChatSession) -> str:
    parts: list[str] = []
    if session.scene:
        parts.append(session.scene)
    if session.message_count > 0:
        parts.append(f"{session.message_count} 条")
    if session.updated_at:
        parts.append(session.updated_at[5:16])
    return " · ".join(parts)


class AiSessionRowWidget(QtWidgets.QFrame):
    """单条会话行：多选时左侧复选框。"""

    clicked = QtCore.Signal()
    double_clicked = QtCore.Signal()
    check_changed = QtCore.Signal(bool)

    MIN_ROW_HEIGHT = 44

    def __init__(
        self,
        *,
        title: str,
        subtitle: str,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("AiSessionRow")
        self.setProperty("active", False)
        self._multi_mode = False

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(6, 6, 8, 6)
        layout.setSpacing(8)

        self._check = QtWidgets.QCheckBox()
        self._check.setObjectName("AiSessionCheck")
        self._check.setVisible(False)
        self._check.toggled.connect(self.check_changed.emit)
        layout.addWidget(self._check, alignment=QtCore.Qt.AlignmentFlag.AlignTop)

        text_col = QtWidgets.QVBoxLayout()
        text_col.setSpacing(2)
        self._text_spacing = 2
        self._title = QtWidgets.QLabel(title)
        self._title.setObjectName("AiSessionRowTitle")
        self._title.setWordWrap(False)
        self._title.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.NoTextInteraction)
        text_col.addWidget(self._title)
        self._subtitle: QtWidgets.QLabel | None = None
        if subtitle:
            self._subtitle = QtWidgets.QLabel(subtitle)
            self._subtitle.setObjectName("AiSessionRowSubtitle")
            self._subtitle.setWordWrap(False)
            self._subtitle.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.NoTextInteraction)
            text_col.addWidget(self._subtitle)
        layout.addLayout(text_col, stretch=1)

        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Minimum,
        )
        self._apply_cursor()

    def _content_height(self) -> int:
        layout = self.layout()
        margins = layout.contentsMargins() if layout is not None else QtCore.QMargins()
        title_h = self._title.sizeHint().height()
        subtitle_h = self._subtitle.sizeHint().height() if self._subtitle is not None else 0
        text_block = title_h + (self._text_spacing if self._subtitle is not None else 0) + subtitle_h
        check_h = self._check.sizeHint().height() if self._check.isVisible() else 0
        content = max(text_block, check_h)
        return margins.top() + content + margins.bottom()

    def sizeHint(self) -> QtCore.QSize:
        return QtCore.QSize(0, max(self.MIN_ROW_HEIGHT, self._content_height()))

    def minimumSizeHint(self) -> QtCore.QSize:
        return self.sizeHint()

    def title_text(self) -> str:
        return self._title.text()

    def set_multi_mode(self, enabled: bool) -> None:
        self._multi_mode = enabled
        self._check.setVisible(enabled)
        if not enabled:
            self._check.setChecked(False)
        self._apply_cursor()

    def set_checked(self, checked: bool) -> None:
        self._check.blockSignals(True)
        self._check.setChecked(checked)
        self._check.blockSignals(False)

    def is_checked(self) -> bool:
        return self._check.isChecked()

    def set_active(self, active: bool) -> None:
        """标记为右侧对话区当前会话（左侧高亮条）。"""
        self.setProperty("active", active)
        self.style().unpolish(self)
        self.style().polish(self)

    def _apply_cursor(self) -> None:
        if self._multi_mode:
            self.setCursor(QtCore.Qt.CursorShape.ArrowCursor)
        else:
            self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            if self._check.isVisible() and self._check.geometry().contains(event.pos()):
                super().mousePressEvent(event)
                return
            if self._multi_mode:
                self._check.setChecked(not self._check.isChecked())
            elif not self._multi_mode:
                self.clicked.emit()
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event: QtGui.QMouseEvent) -> None:
        if not self._multi_mode:
            self.double_clicked.emit()
        super().mouseDoubleClickEvent(event)


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
        self._multi_checked_ids: set[str] = set()
        self._rows_by_id: dict[str, AiSessionRowWidget] = {}
        self._items_by_id: dict[str, QtWidgets.QListWidgetItem] = {}
        self.setObjectName("AiSessionList")
        bind_ai_panel_style(self)
        self._build_ui()
        self.engine.signals.sessions_changed.connect(self.refresh)
        self.engine.signals.messages_changed.connect(self._sync_active_session_highlight)
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
        self._list.setWordWrap(True)
        self._list.setTextElideMode(QtCore.Qt.TextElideMode.ElideNone)
        self._list.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.NoSelection)
        self._list.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self._list.customContextMenuRequested.connect(self._on_context_menu)
        root.addWidget(self._list, stretch=1)

    def _on_multi_select_toggled(self, checked: bool) -> None:
        self._set_multi_select_mode(checked)

    def _set_multi_select_mode(
        self,
        enabled: bool,
        *,
        preselect_session_id: str | None = None,
    ) -> None:
        if self._multi_select_mode == enabled and preselect_session_id is None:
            return
        self._multi_select_mode = enabled
        if self._multi_btn.isChecked() != enabled:
            self._multi_btn.blockSignals(True)
            self._multi_btn.setChecked(enabled)
            self._multi_btn.blockSignals(False)
        if enabled:
            self._multi_btn.setText("取消")
            self._multi_btn.setToolTip("退出多选模式")
            if preselect_session_id:
                self._multi_checked_ids.add(preselect_session_id)
        else:
            self._multi_btn.setText("多选")
            self._multi_btn.setToolTip("多选删除会话")
            self._multi_checked_ids.clear()
        self._sync_active_session_highlight()
        for session_id, row in self._rows_by_id.items():
            row.set_multi_mode(enabled)
            if enabled:
                row.set_checked(session_id in self._multi_checked_ids)
        self._update_multi_select_ui()

    def _sync_active_session_highlight(self) -> None:
        """按 engine.session_id 同步当前对话高亮（右侧聊天区正在展示的会话）。"""
        current_id = self.engine.session_id
        for session_id, row in self._rows_by_id.items():
            active = session_id == current_id
            if not self._multi_select_mode:
                row.set_active(active)
            else:
                row.set_active(False)

    def _update_multi_select_ui(self) -> None:
        count = len(self._multi_checked_ids)
        if self._multi_select_mode:
            self._del_btn.setVisible(count >= 1)
            self._del_btn.setText(f"删除({count})" if count else "删除选中")
        else:
            self._del_btn.setVisible(False)
            self._del_btn.setText("删除选中")

    def refresh(self) -> None:
        checked_ids = set(self._multi_checked_ids)
        current_id = self.engine.session_id
        self._list.clear()
        self._rows_by_id.clear()
        self._items_by_id.clear()
        sessions = self.engine.list_sessions()
        for session in sessions:
            subtitle = _format_session_subtitle(session)
            active = session.id == current_id
            row = AiSessionRowWidget(
                title=session.title,
                subtitle=subtitle,
            )
            row.set_multi_mode(self._multi_select_mode)
            if self._multi_select_mode:
                row.set_checked(session.id in checked_ids)
            else:
                row.set_active(active)

            item = QtWidgets.QListWidgetItem()
            item.setData(_SESSION_ID_ROLE, session.id)
            item.setToolTip(f"{session.title}\n更新于 {session.updated_at}")
            row.adjustSize()
            item.setSizeHint(row.sizeHint())
            self._list.addItem(item)
            self._list.setItemWidget(item, row)

            session_id = session.id
            self._rows_by_id[session_id] = row
            self._items_by_id[session_id] = item
            row.clicked.connect(lambda sid=session_id: self._on_row_clicked(sid))
            row.double_clicked.connect(lambda sid=session_id: self._on_row_double_clicked(sid))
            row.check_changed.connect(
                lambda checked, sid=session_id: self._on_row_check_changed(sid, checked),
            )

        if self._multi_select_mode:
            existing_ids = set(self._rows_by_id)
            self._multi_checked_ids = {sid for sid in checked_ids if sid in existing_ids}
            self._update_multi_select_ui()
        else:
            self._sync_active_session_highlight()

    def _on_row_check_changed(self, session_id: str, checked: bool) -> None:
        if checked:
            self._multi_checked_ids.add(session_id)
        else:
            self._multi_checked_ids.discard(session_id)
        self._update_multi_select_ui()

    def _selected_sessions(self) -> list[tuple[str, str]]:
        result: list[tuple[str, str]] = []
        for session_id in self._multi_checked_ids:
            row = self._rows_by_id.get(session_id)
            if row is not None:
                result.append((session_id, row.title_text()))
        return result

    def _on_delete_selected(self) -> None:
        selected = self._selected_sessions()
        if not selected:
            return
        count = len(selected)
        title_line = f"确定要删除选中的 {count} 个会话及其全部消息吗？"
        if count == 1:
            title_line = f"确定要删除会话「{selected[0][1]}」及其全部消息吗？"
        detail = title_line + ("\n\n" + "\n".join(f"  · {title}" for _, title in selected) if count > 1 else "")
        if not confirm_action(
            self,
            "确认删除",
            detail,
            confirm_text="删除",
            destructive=True,
        ):
            return
        for session_id, _ in selected:
            self.engine.delete_session(session_id)
        self._set_multi_select_mode(False)

    def _on_row_clicked(self, session_id: str) -> None:
        if self._multi_select_mode:
            return
        if self.engine.is_busy():
            page_notify(self, "请等待当前回复完成后再切换会话")
            return
        self.engine.switch_session(session_id)
        self._sync_active_session_highlight()
        self.session_selected.emit(session_id)
        if self._close_on_select and self._close_parent is not None:
            self._close_parent.close()

    def _on_row_double_clicked(self, session_id: str) -> None:
        if self._multi_select_mode:
            row = self._rows_by_id.get(session_id)
            if row is not None:
                row.set_checked(not row.is_checked())
                if row.is_checked():
                    self._multi_checked_ids.add(session_id)
                else:
                    self._multi_checked_ids.discard(session_id)
                self._update_multi_select_ui()
            return
        item = self._items_by_id.get(session_id)
        if item is not None:
            self._rename_item(item)

    def _on_new_session(self) -> None:
        if self.engine.is_busy():
            page_notify(self, "请等待当前回复完成后再新建会话")
            return
        self.engine.new_session()

    def _select_all(self) -> None:
        for session_id, row in self._rows_by_id.items():
            row.set_checked(True)
            self._multi_checked_ids.add(session_id)
        self._update_multi_select_ui()

    def _on_context_menu(self, pos: QtCore.QPoint) -> None:
        item = self._list.itemAt(pos)
        session_id: str | None = None
        if item is not None:
            raw = item.data(_SESSION_ID_ROLE)
            session_id = str(raw) if raw else None
        selected = self._selected_sessions()
        menu = QtWidgets.QMenu(self)

        if self._multi_select_mode:
            if selected:
                menu.addAction(
                    f"删除选中的 {len(selected)} 个会话",
                    self._on_delete_selected,
                )
            menu.addAction("全选", self._select_all)
            menu.addAction("取消多选", lambda: self._set_multi_select_mode(False))
            menu.exec(self._list.mapToGlobal(pos))
            return

        enter_multi = menu.addAction("多选")
        if session_id is not None:
            item_title = self._rows_by_id[session_id].title_text() if session_id in self._rows_by_id else ""
            menu.addSeparator()
            menu.addAction("重命名", lambda: self._rename_session(session_id, item_title))
            menu.addAction(
                "删除",
                lambda: self._delete_session(session_id, item_title),
            )
        action = menu.exec(self._list.mapToGlobal(pos))
        if action is enter_multi:
            self._set_multi_select_mode(True, preselect_session_id=session_id)

    def _rename_item(self, item: QtWidgets.QListWidgetItem) -> None:
        session_id = item.data(_SESSION_ID_ROLE)
        if not session_id:
            return
        row = self._rows_by_id.get(str(session_id))
        title = row.title_text() if row is not None else item.text().split("\n", 1)[0]
        self._rename_session(str(session_id), title)

    def _rename_session(self, session_id: str, current_title: str) -> None:
        text, ok = QtWidgets.QInputDialog.getText(
            self,
            "重命名会话",
            "会话标题",
            QtWidgets.QLineEdit.EchoMode.Normal,
            current_title,
        )
        if ok and text.strip():
            self.engine.rename_session(session_id, text.strip())

    def _delete_session(self, session_id: str, title: str) -> None:
        if confirm_action(
            self,
            "确认删除",
            f"删除会话「{title}」及其全部消息？",
            confirm_text="删除",
            destructive=True,
        ):
            self.engine.delete_session(session_id)


class AiSessionSidebar(QtWidgets.QWidget):
    """全屏页左侧会话栏（可折叠、可拖拽调宽）。"""

    CONTENT_MIN_WIDTH = 240
    DEFAULT_CONTENT_WIDTH = 300
    RAIL_WIDTH = 32

    @classmethod
    def default_width(cls) -> int:
        return cls.DEFAULT_CONTENT_WIDTH + cls.RAIL_WIDTH

    def __init__(self, engine: LlmEngine, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("AiSessionSidebar")
        self._expanded = True
        self._apply_width_constraints(expanded=True)
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Preferred,
            QtWidgets.QSizePolicy.Policy.Expanding,
        )
        bind_ai_panel_style(self)

        root = QtWidgets.QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._content = QtWidgets.QWidget(self)
        self._content.setMinimumWidth(self.CONTENT_MIN_WIDTH)
        self._content.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Expanding,
        )
        content_layout = QtWidgets.QVBoxLayout(self._content)
        content_layout.setContentsMargins(10, 10, 6, 10)
        content_layout.setSpacing(0)
        self._list = AiSessionListWidget(engine, parent=self._content)
        content_layout.addWidget(self._list)
        root.addWidget(self._content, stretch=1)

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

    def _splitter(self) -> QtWidgets.QSplitter | None:
        parent = self.parentWidget()
        return parent if isinstance(parent, QtWidgets.QSplitter) else None

    def _apply_width_constraints(self, *, expanded: bool) -> None:
        if expanded:
            self.setMinimumWidth(self.CONTENT_MIN_WIDTH + self.RAIL_WIDTH)
            self.setMaximumWidth(16777215)
        else:
            self.setMinimumWidth(self.RAIL_WIDTH)
            self.setMaximumWidth(self.RAIL_WIDTH)

    def _toggle_expanded(self) -> None:
        self.set_expanded(not self._expanded)

    def set_expanded(self, expanded: bool) -> None:
        if self._expanded == expanded:
            return
        self._expanded = expanded
        self._content.setVisible(expanded)
        self._apply_width_constraints(expanded=expanded)
        splitter = self._splitter()
        if splitter is not None:
            sizes = splitter.sizes()
            total = max(sum(sizes), self.default_width() + 400)
            if expanded:
                restored = max(self.default_width(), min(sizes[0], total // 2))
                splitter.setSizes([restored, total - restored])
            else:
                splitter.setSizes([self.RAIL_WIDTH, total - self.RAIL_WIDTH])
        if expanded:
            self._toggle_btn.setText("◀")
            self._toggle_btn.setToolTip("收起历史会话")
        else:
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
        bind_ai_panel_style(self)

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        session_list = AiSessionListWidget(engine, close_on_select=True, parent=self)
        session_list.set_close_parent(self)
        root.addWidget(session_list)


def show_ai_session_dialog(engine: LlmEngine, parent: QtWidgets.QWidget | None = None) -> None:
    dialog = AiSessionDialog(engine, parent)
    dialog.exec()
