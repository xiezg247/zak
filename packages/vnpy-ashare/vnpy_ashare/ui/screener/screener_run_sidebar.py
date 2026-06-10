"""选股历史侧栏（策略选股 / 自动选股共用）。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from vnpy.trader.ui import QtCore, QtGui, QtWidgets

from vnpy_ashare.app.engine_access import get_screening_service
from vnpy_common.paths import QSETTINGS_ORG
from vnpy_ashare.screener.run_store import (
    delete_run,
    is_auto_run,
    is_run_unread,
    is_strategy_run,
    list_runs,
)
from vnpy_common.ui.theme import theme_manager

if TYPE_CHECKING:
    from vnpy.trader.engine import MainEngine

    from vnpy_ashare.services.screening_service import ScreeningService

_RUN_ID_ROLE = QtCore.Qt.ItemDataRole.UserRole
_RUN_CONDITION_ROLE = QtCore.Qt.ItemDataRole.UserRole + 1

SidebarMode = Literal["strategy", "auto"]

_FILTER_ALL = "all"
_FILTER_INTRADAY = "intraday"
_FILTER_POST_CLOSE = "post_close"

_TRIGGER_TAGS = {
    "scheduled_intraday": "[盘中]",
    "scheduled_post_close": "[盘后]",
}

_SETTINGS_ORG = QSETTINGS_ORG
_SETTINGS_APP = "screener_ui"


# 侧栏数据访问：优先 ScreeningService Facade；无 Engine 时 fallback run_store（测试/headless）


def _screening_from_engine(main_engine: MainEngine | None) -> ScreeningService | None:
    return get_screening_service(main_engine)


def _list_runs(main_engine: MainEngine | None, limit: int = 40):
    service = _screening_from_engine(main_engine)
    if service is not None:
        return service.list_run_history(limit)

    return list_runs(limit=limit)


def _delete_run(main_engine: MainEngine | None, run_id: str) -> None:
    service = _screening_from_engine(main_engine)
    if service is not None:
        service.delete_run_record(run_id)
        return

    delete_run(run_id)


def _is_auto_run(main_engine: MainEngine | None, config) -> bool:
    service = _screening_from_engine(main_engine)
    if service is not None:
        return service.is_auto_run_config(config)

    return is_auto_run(config)


def _is_strategy_run(main_engine: MainEngine | None, config) -> bool:
    service = _screening_from_engine(main_engine)
    if service is not None:
        return service.is_strategy_run_config(config)

    return is_strategy_run(config)


def _is_run_unread(main_engine: MainEngine | None, config) -> bool:
    service = _screening_from_engine(main_engine)
    if service is not None:
        return service.is_run_unread_config(config)

    return is_run_unread(config)


def _run_filter_label(record) -> str:
    trigger = str(record.config.get("trigger", ""))
    tag = _TRIGGER_TAGS.get(trigger, "")
    if trigger.startswith("ai_"):
        tag = "[AI]"
    title = record.condition
    if tag and not title.startswith("["):
        title = f"{tag} {title}"
    return title


class ScreenerRunRowWidget(QtWidgets.QFrame):
    """自动结果列表行：多选时左侧复选框。"""

    clicked = QtCore.Signal()
    double_clicked = QtCore.Signal()
    check_changed = QtCore.Signal(bool)

    MIN_ROW_HEIGHT = 44

    def __init__(
        self,
        *,
        title: str,
        subtitle: str,
        unread: bool = False,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("ScreenerRunRow")
        self.setProperty("active", False)
        self._multi_mode = False

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(6, 6, 8, 6)
        layout.setSpacing(8)

        self._check = QtWidgets.QCheckBox()
        self._check.setObjectName("ScreenerRunCheck")
        self._check.setVisible(False)
        self._check.toggled.connect(self.check_changed.emit)
        layout.addWidget(self._check, alignment=QtCore.Qt.AlignmentFlag.AlignTop)

        text_col = QtWidgets.QVBoxLayout()
        text_col.setSpacing(2)
        self._text_spacing = 2
        self._title = QtWidgets.QLabel(title)
        self._title.setObjectName("ScreenerRunRowTitle")
        self._title.setWordWrap(False)
        self._title.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.NoTextInteraction)
        if unread:
            font = self._title.font()
            font.setBold(True)
            self._title.setFont(font)
            self._title.setStyleSheet(f"color: {theme_manager().tokens().run_row_unread};")
        text_col.addWidget(self._title)
        self._subtitle = QtWidgets.QLabel(subtitle)
        self._subtitle.setObjectName("ScreenerRunRowSubtitle")
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
        subtitle_h = self._subtitle.sizeHint().height()
        text_block = title_h + self._text_spacing + subtitle_h
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
            else:
                self.clicked.emit()
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event: QtGui.QMouseEvent) -> None:
        if not self._multi_mode:
            self.double_clicked.emit()
        super().mouseDoubleClickEvent(event)


class ScreenerRunListWidget(QtWidgets.QWidget):
    """可复用的选股历史列表。"""

    run_selected = QtCore.Signal(str)
    copy_run_id_requested = QtCore.Signal(str, str)
    ask_ai_requested = QtCore.Signal(str, str)
    runs_deleted = QtCore.Signal(list)

    def __init__(
        self,
        *,
        mode: SidebarMode = "strategy",
        main_engine: MainEngine | None = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("ScreenerRunList")
        self._mode = mode
        self._main_engine = main_engine
        self._filter = _FILTER_ALL
        self._multi_select_mode = False
        self._multi_checked_ids: set[str] = set()
        self._rows_by_id: dict[str, ScreenerRunRowWidget] = {}
        self._items_by_id: dict[str, QtWidgets.QListWidgetItem] = {}
        self._current_run_id: str | None = None
        self._multi_btn: QtWidgets.QPushButton | None = None
        self._del_btn: QtWidgets.QPushButton | None = None
        self._build_ui()
        theme_manager().bind_stylesheet(self)
        theme_manager().register_callback(lambda _tokens: self.refresh())
        self.refresh()

    def _resolve_main_engine(self) -> MainEngine | None:
        if self._main_engine is not None:
            return self._main_engine
        parent = self.parent()
        while parent is not None:
            engine = getattr(parent, "main_engine", None)
            if engine is not None:
                return engine
            parent = parent.parent()
        return None

    def _build_ui(self) -> None:
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        title = QtWidgets.QLabel("自动结果" if self._mode == "auto" else "历史运行")
        title.setObjectName("AiSessionTitle")
        root.addWidget(title)

        if self._mode == "auto":
            self._filter_tabs = QtWidgets.QTabBar()
            self._filter_tabs.setObjectName("ScreenerRunFilterTabs")
            self._filter_tabs.addTab("全部")
            self._filter_tabs.addTab("盘中")
            self._filter_tabs.addTab("盘后")
            self._filter_tabs.currentChanged.connect(self._on_filter_changed)
            root.addWidget(self._filter_tabs)

        actions_row = QtWidgets.QHBoxLayout()
        actions_row.setSpacing(6)
        self._multi_btn = QtWidgets.QPushButton("多选")
        self._multi_btn.setObjectName("SecondaryButton")
        self._multi_btn.setCheckable(True)
        self._multi_btn.setToolTip(self._multi_select_tooltip())
        self._multi_btn.toggled.connect(self._on_multi_select_toggled)
        actions_row.addWidget(self._multi_btn)
        self._del_btn = QtWidgets.QPushButton("删除选中")
        self._del_btn.setObjectName("DangerButton")
        self._del_btn.setVisible(False)
        self._del_btn.clicked.connect(self._on_delete_selected)
        actions_row.addWidget(self._del_btn)
        actions_row.addStretch()
        root.addLayout(actions_row)

        self._list = QtWidgets.QListWidget()
        self._list.setObjectName("AiSessionListWidget")
        self._list.setSpacing(2)
        self._list.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.NoSelection)
        self._list.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self._list.customContextMenuRequested.connect(self._on_context_menu)
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

    def unread_count(self) -> int:
        main_engine = self._resolve_main_engine()
        count = 0
        for record in _list_runs(main_engine, limit=40):
            if not self._matches_mode(record, main_engine):
                continue
            if not self._matches_subfilter(record):
                continue
            if _is_run_unread(main_engine, record.config):
                count += 1
        return count

    def _run_kind_label(self) -> str:
        return "自动结果" if self._mode == "auto" else "历史运行"

    def _multi_select_tooltip(self) -> str:
        return f"多选删除{self._run_kind_label()}"

    def _on_filter_changed(self, index: int) -> None:
        filters = [_FILTER_ALL, _FILTER_INTRADAY, _FILTER_POST_CLOSE]
        self._filter = filters[index] if 0 <= index < len(filters) else _FILTER_ALL
        self.refresh()

    def _matches_mode(self, record, main_engine: MainEngine | None) -> bool:
        if self._mode == "strategy":
            return _is_strategy_run(main_engine, record.config)
        return _is_auto_run(main_engine, record.config)

    def _matches_subfilter(self, record) -> bool:
        if self._mode != "auto" or self._filter == _FILTER_ALL:
            return True
        trigger = str(record.config.get("trigger", ""))
        if self._filter == _FILTER_INTRADAY:
            return trigger == "scheduled_intraday"
        if self._filter == _FILTER_POST_CLOSE:
            return trigger == "scheduled_post_close"
        return True

    def _selected_item(self) -> QtWidgets.QListWidgetItem | None:
        if not self._current_run_id:
            return None
        return self._items_by_id.get(self._current_run_id)

    def _selected_run(self) -> tuple[str, str] | None:
        run_id = self._current_run_id
        if not run_id:
            return None
        row = self._rows_by_id.get(run_id)
        item = self._items_by_id.get(run_id)
        if row is None and item is None:
            return None
        condition = ""
        if item is not None:
            condition = str(item.data(_RUN_CONDITION_ROLE) or "")
        if not condition and row is not None:
            condition = row.title_text()
        return run_id, condition

    def _update_action_buttons(self) -> None:
        enabled = self._selected_run() is not None and not self._multi_select_mode
        self._copy_btn.setEnabled(enabled)
        self._ask_ai_btn.setEnabled(enabled)

    def _on_multi_select_toggled(self, checked: bool) -> None:
        self._set_multi_select_mode(checked)

    def _set_multi_select_mode(
        self,
        enabled: bool,
        *,
        preselect_run_id: str | None = None,
    ) -> None:
        if self._multi_select_mode == enabled and preselect_run_id is None:
            return
        self._multi_select_mode = enabled
        if self._multi_btn is not None and self._multi_btn.isChecked() != enabled:
            self._multi_btn.blockSignals(True)
            self._multi_btn.setChecked(enabled)
            self._multi_btn.blockSignals(False)
        if enabled:
            if self._multi_btn is not None:
                self._multi_btn.setText("取消")
                self._multi_btn.setToolTip("退出多选模式")
            if preselect_run_id:
                self._multi_checked_ids.add(preselect_run_id)
        else:
            if self._multi_btn is not None:
                self._multi_btn.setText("多选")
                self._multi_btn.setToolTip(self._multi_select_tooltip())
            self._multi_checked_ids.clear()
        self._sync_active_run_highlight()
        for run_id, row in self._rows_by_id.items():
            row.set_multi_mode(enabled)
            if enabled:
                row.set_checked(run_id in self._multi_checked_ids)
        self._update_multi_select_ui()
        self._update_action_buttons()

    def _sync_active_run_highlight(self) -> None:
        for run_id, row in self._rows_by_id.items():
            active = run_id == self._current_run_id
            if not self._multi_select_mode:
                row.set_active(active)
            else:
                row.set_active(False)

    def _update_multi_select_ui(self) -> None:
        if self._del_btn is None:
            return
        count = len(self._multi_checked_ids)
        if self._multi_select_mode:
            self._del_btn.setVisible(count >= 1)
            self._del_btn.setText(f"删除({count})" if count else "删除选中")
        else:
            self._del_btn.setVisible(False)
            self._del_btn.setText("删除选中")

    def refresh(self) -> None:
        self._refresh_list()
        self._notify_sidebar_badge()

    def _notify_sidebar_badge(self) -> None:
        parent = self.parent()
        while parent is not None:
            if isinstance(parent, ScreenerRunSidebar):
                if getattr(parent, "_list", None) is self:
                    parent._update_rail_badge()
                break
            parent = parent.parent()

    def _refresh_list(self) -> None:
        main_engine = self._resolve_main_engine()
        checked_ids = set(self._multi_checked_ids)
        selected_id = self._current_run_id
        self._list.clear()
        self._rows_by_id.clear()
        self._items_by_id.clear()
        restore_id: str | None = None
        first_id: str | None = None
        for record in _list_runs(main_engine, limit=40):
            if not self._matches_mode(record, main_engine):
                continue
            if not self._matches_subfilter(record):
                continue
            if first_id is None:
                first_id = record.id
            title = _run_filter_label(record)
            subtitle = f"{record.row_count} 条 · {record.created_at[5:16]}"
            unread = _is_run_unread(main_engine, record.config)
            active = record.id == selected_id
            row = ScreenerRunRowWidget(title=title, subtitle=subtitle, unread=unread)
            row.set_multi_mode(self._multi_select_mode)
            if self._multi_select_mode:
                row.set_checked(record.id in checked_ids)
            else:
                row.set_active(active)
            reason = record.config.get("reason_summary") or record.config.get("trigger", "")
            item = QtWidgets.QListWidgetItem()
            item.setData(_RUN_ID_ROLE, record.id)
            item.setData(_RUN_CONDITION_ROLE, record.condition)
            item.setToolTip(
                f"{title}\nrun_id: {record.id}\n来源 {record.source} · 扫描 {record.total_scanned} · {record.created_at}\n{reason}",
            )
            row.adjustSize()
            item.setSizeHint(row.sizeHint())
            self._list.addItem(item)
            self._list.setItemWidget(item, row)
            run_id = record.id
            self._rows_by_id[run_id] = row
            self._items_by_id[run_id] = item
            row.clicked.connect(lambda rid=run_id: self._on_row_clicked(rid))
            row.check_changed.connect(
                lambda checked, rid=run_id: self._on_row_check_changed(rid, checked),
            )
            if selected_id and record.id == selected_id:
                restore_id = record.id
        if self._multi_select_mode:
            existing_ids = set(self._rows_by_id)
            self._multi_checked_ids = {rid for rid in checked_ids if rid in existing_ids}
            self._update_multi_select_ui()
        else:
            if restore_id is not None:
                self._current_run_id = restore_id
            elif first_id is not None and self._current_run_id is None:
                self._current_run_id = first_id
            elif self._current_run_id not in self._rows_by_id:
                self._current_run_id = first_id
            self._sync_active_run_highlight()
        self._update_action_buttons()

    def _on_row_clicked(self, run_id: str) -> None:
        if self._multi_select_mode:
            return
        self._current_run_id = run_id
        self._sync_active_run_highlight()
        self.run_selected.emit(run_id)

    def _on_row_check_changed(self, run_id: str, checked: bool) -> None:
        if checked:
            self._multi_checked_ids.add(run_id)
        else:
            self._multi_checked_ids.discard(run_id)
        self._update_multi_select_ui()

    def _selected_runs(self) -> list[tuple[str, str]]:
        result: list[tuple[str, str]] = []
        for run_id in self._multi_checked_ids:
            row = self._rows_by_id.get(run_id)
            if row is not None:
                result.append((run_id, row.title_text()))
        return result

    def _on_delete_selected(self) -> None:
        selected = self._selected_runs()
        if not selected:
            return
        count = len(selected)
        kind = self._run_kind_label()
        title_line = f"确定要删除选中的 {count} 条{kind}吗？"
        if count == 1:
            title_line = f"确定要删除{kind}「{selected[0][1]}」？"
        reply = QtWidgets.QMessageBox.question(
            self,
            "确认删除",
            title_line + ("\n\n" + "\n".join(f"  · {title}" for _, title in selected) if count > 1 else ""),
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
        )
        if reply != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        deleted_ids = [run_id for run_id, _ in selected]
        main_engine = self._resolve_main_engine()
        for run_id in deleted_ids:
            _delete_run(main_engine, run_id)
        if self._current_run_id in deleted_ids:
            self._current_run_id = None
        self.runs_deleted.emit(deleted_ids)
        self._set_multi_select_mode(False)
        self.refresh()

    def _select_all_runs(self) -> None:
        for run_id, row in self._rows_by_id.items():
            row.set_checked(True)
            self._multi_checked_ids.add(run_id)
        self._update_multi_select_ui()

    def _delete_run_with_confirm(self, run_id: str, title: str) -> None:
        reply = QtWidgets.QMessageBox.question(
            self,
            "确认删除",
            f"删除{self._run_kind_label()}「{title}」？",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
        )
        if reply != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        _delete_run(self._resolve_main_engine(), run_id)
        if self._current_run_id == run_id:
            self._current_run_id = None
        self.runs_deleted.emit([run_id])
        self.refresh()

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
        run_id: str | None = None
        condition = ""
        title = ""
        if item is not None:
            raw = item.data(_RUN_ID_ROLE)
            run_id = str(raw) if raw else None
            condition = str(item.data(_RUN_CONDITION_ROLE) or "")
            if run_id in self._rows_by_id:
                title = self._rows_by_id[run_id].title_text()
            else:
                title = item.text().split("\n", 1)[0]
            if not condition:
                condition = title

        selected = self._selected_runs()
        menu = QtWidgets.QMenu(self)
        if self._multi_select_mode:
            if selected:
                menu.addAction(
                    f"删除选中的 {len(selected)} 条",
                    self._on_delete_selected,
                )
            menu.addAction("全选", self._select_all_runs)
            menu.addAction("取消多选", lambda: self._set_multi_select_mode(False))
            menu.exec(self._list.mapToGlobal(pos))
            return

        enter_multi = menu.addAction("多选")
        if run_id is not None:
            menu.addSeparator()
            copy_action = menu.addAction("复制 run_id")
            ask_action = menu.addAction("发给 AI 解读")
            menu.addSeparator()
            delete_action = menu.addAction("删除")
            action = menu.exec(self._list.mapToGlobal(pos))
            if action is copy_action:
                QtWidgets.QApplication.clipboard().setText(run_id)
                self.copy_run_id_requested.emit(run_id, condition)
            elif action is ask_action:
                self.ask_ai_requested.emit(run_id, condition)
            elif action is delete_action:
                self._delete_run_with_confirm(run_id, title)
            elif action is enter_multi:
                self._set_multi_select_mode(True, preselect_run_id=run_id)
        else:
            action = menu.exec(self._list.mapToGlobal(pos))
            if action is enter_multi:
                self._set_multi_select_mode(True)


class ScreenerRunSidebar(QtWidgets.QWidget):
    """左侧历史栏（可折叠）。"""

    run_selected = QtCore.Signal(str)
    copy_run_id_requested = QtCore.Signal(str, str)
    ask_ai_requested = QtCore.Signal(str, str)
    runs_deleted = QtCore.Signal(list)

    CONTENT_WIDTH = 200
    AUTO_CONTENT_WIDTH = 260
    RAIL_WIDTH = 36

    def __init__(
        self,
        *,
        mode: SidebarMode = "strategy",
        main_engine: MainEngine | None = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._main_engine = main_engine
        self._mode = mode
        self._content_width = self.AUTO_CONTENT_WIDTH if mode == "auto" else self.CONTENT_WIDTH
        self.setObjectName("AiSessionSidebar")
        self._expanded = False
        self.setFixedWidth(self.RAIL_WIDTH)

        root = QtWidgets.QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._content = QtWidgets.QWidget(self)
        self._content.setFixedWidth(self._content_width)
        self._content.setVisible(False)
        content_layout = QtWidgets.QVBoxLayout(self._content)
        content_layout.setContentsMargins(12, 12, 4, 12)
        content_layout.setSpacing(0)
        self._list = ScreenerRunListWidget(mode=mode, main_engine=main_engine, parent=self._content)
        self._list.run_selected.connect(self.run_selected.emit)
        self._list.copy_run_id_requested.connect(self.copy_run_id_requested.emit)
        self._list.ask_ai_requested.connect(self.ask_ai_requested.emit)
        self._list.runs_deleted.connect(self.runs_deleted.emit)
        content_layout.addWidget(self._list)
        root.addWidget(self._content)

        rail = QtWidgets.QWidget(self)
        rail.setObjectName("AiSessionRail")
        rail.setFixedWidth(self.RAIL_WIDTH)
        rail_layout = QtWidgets.QVBoxLayout(rail)
        rail_layout.setContentsMargins(0, 12, 0, 12)
        rail_layout.addStretch()

        self._badge = QtWidgets.QLabel("")
        self._badge.setObjectName("ScreenerUnreadBadge")
        self._badge.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._badge.setFixedHeight(16)
        self._badge.hide()

        self._toggle_btn = QtWidgets.QToolButton()
        self._toggle_btn.setObjectName("AiSessionToggle")
        self._toggle_btn.setText("▶")
        tooltip = "展开自动结果" if mode == "auto" else "展开历史运行"
        self._toggle_btn.setToolTip(tooltip)
        self._toggle_btn.setFixedSize(28, 28)
        self._toggle_btn.clicked.connect(self._toggle_expanded)

        rail_layout.addWidget(self._badge, alignment=QtCore.Qt.AlignmentFlag.AlignHCenter)
        rail_layout.addWidget(self._toggle_btn, alignment=QtCore.Qt.AlignmentFlag.AlignHCenter)
        rail_layout.addStretch()
        root.addWidget(rail)
        theme_manager().bind_stylesheet(self)
        self._restore_expanded_preference()

    def _settings_key(self) -> str:
        return f"{self._mode}_sidebar_expanded"

    def _load_expanded_preference(self) -> bool:
        settings = QtCore.QSettings(_SETTINGS_ORG, _SETTINGS_APP)
        value = settings.value(self._settings_key(), False)
        if isinstance(value, str):
            return value.lower() in ("1", "true", "yes")
        return bool(value)

    def _save_expanded_preference(self) -> None:
        settings = QtCore.QSettings(_SETTINGS_ORG, _SETTINGS_APP)
        settings.setValue(self._settings_key(), self._expanded)

    def _restore_expanded_preference(self) -> None:
        if self._load_expanded_preference():
            self.set_expanded(True, persist=False)
        else:
            self._update_rail_badge()

    def _update_rail_badge(self) -> None:
        if self._expanded:
            self._badge.hide()
            return
        count = self._list.unread_count()
        if count <= 0:
            self._badge.hide()
            return
        self._badge.setText(str(count) if count <= 9 else "9+")
        self._badge.setToolTip(f"{count} 条未读结果")
        self._badge.show()

    def refresh(self) -> None:
        self._list.refresh()
        self._update_rail_badge()

    def set_expanded(self, expanded: bool, *, persist: bool = True) -> None:
        if self._expanded == expanded:
            return
        self._expanded = expanded
        self._content.setVisible(expanded)
        if expanded:
            self.setFixedWidth(self._content_width + self.RAIL_WIDTH)
            self._toggle_btn.setText("◀")
            self._toggle_btn.setToolTip("收起自动结果" if self._mode == "auto" else "收起历史运行")
        else:
            self.setFixedWidth(self.RAIL_WIDTH)
            self._toggle_btn.setText("▶")
            self._toggle_btn.setToolTip("展开自动结果" if self._mode == "auto" else "展开历史运行")
        if persist:
            self._save_expanded_preference()
        self._update_rail_badge()

    def _toggle_expanded(self) -> None:
        self.set_expanded(not self._expanded)
