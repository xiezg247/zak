"""选股历史侧栏（策略选股 / 自动选股共用）。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from vnpy.trader.ui import QtCore, QtGui, QtWidgets

from vnpy_ashare.engine_access import get_screening_service
from vnpy_ashare.ui.styles import TERMINAL_STYLESHEET

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

_SETTINGS_ORG = "vnpy_zak"
_SETTINGS_APP = "screener_ui"


def _screening_from_engine(main_engine: MainEngine | None) -> ScreeningService | None:
    return get_screening_service(main_engine)


def _list_runs(main_engine: MainEngine | None, limit: int = 40):
    service = _screening_from_engine(main_engine)
    if service is not None:
        return service.list_run_history(limit)
    from vnpy_ashare.screener.run_store import list_runs

    return list_runs(limit=limit)


def _delete_run(main_engine: MainEngine | None, run_id: str) -> None:
    service = _screening_from_engine(main_engine)
    if service is not None:
        service.delete_run_record(run_id)
        return
    from vnpy_ashare.screener.run_store import delete_run

    delete_run(run_id)


def _is_auto_run(main_engine: MainEngine | None, config) -> bool:
    service = _screening_from_engine(main_engine)
    if service is not None:
        return service.is_auto_run_config(config)
    from vnpy_ashare.screener.run_store import is_auto_run

    return is_auto_run(config)


def _is_strategy_run(main_engine: MainEngine | None, config) -> bool:
    service = _screening_from_engine(main_engine)
    if service is not None:
        return service.is_strategy_run_config(config)
    from vnpy_ashare.screener.run_store import is_strategy_run

    return is_strategy_run(config)


def _is_run_unread(main_engine: MainEngine | None, config) -> bool:
    service = _screening_from_engine(main_engine)
    if service is not None:
        return service.is_run_unread_config(config)
    from vnpy_ashare.screener.run_store import is_run_unread

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


class ScreenerRunListWidget(QtWidgets.QWidget):
    """可复用的选股历史列表。"""

    run_selected = QtCore.Signal(str)
    copy_run_id_requested = QtCore.Signal(str, str)
    ask_ai_requested = QtCore.Signal(str, str)

    def __init__(
        self,
        *,
        mode: SidebarMode = "strategy",
        main_engine: MainEngine | None = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("ScreenerRunList")
        self.setStyleSheet(TERMINAL_STYLESHEET)
        self._mode = mode
        self._main_engine = main_engine
        self._filter = _FILTER_ALL
        self._build_ui()
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
        main_engine = self._resolve_main_engine()
        selected_id = None
        current = self._selected_run()
        if current is not None:
            selected_id = current[0]
        self._list.clear()
        restore_row = -1
        for record in _list_runs(main_engine, limit=40):
            if not self._matches_mode(record, main_engine):
                continue
            if not self._matches_subfilter(record):
                continue
            title = _run_filter_label(record)
            subtitle = f"{record.row_count} 条 · {record.created_at[5:16]}"
            display = f"{title}\n{subtitle}"
            item = QtWidgets.QListWidgetItem(display)
            item.setData(_RUN_ID_ROLE, record.id)
            item.setData(_RUN_CONDITION_ROLE, record.condition)
            if _is_run_unread(main_engine, record.config):
                font = item.font()
                font.setBold(True)
                item.setFont(font)
                item.setForeground(QtGui.QColor("#7dd3fc"))
            reason = record.config.get("reason_summary") or record.config.get("trigger", "")
            item.setToolTip(f"{title}\nrun_id: {record.id}\n来源 {record.source} · 扫描 {record.total_scanned} · {record.created_at}\n{reason}")
            self._list.addItem(item)
            if selected_id and record.id == selected_id:
                restore_row = self._list.count() - 1
        if restore_row >= 0:
            self._list.setCurrentRow(restore_row)
        elif self._list.count() > 0:
            self._list.setCurrentRow(0)
        self._update_action_buttons()
        parent = self.parent()
        while parent is not None:
            if isinstance(parent, ScreenerRunSidebar):
                # 侧栏 __init__ 中创建列表时会同步 refresh，此时尚未赋值 self._list
                if getattr(parent, "_list", None) is self:
                    parent._update_rail_badge()
                break
            parent = parent.parent()

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
                _delete_run(self._resolve_main_engine(), str(run_id))
                self.refresh()


class ScreenerRunSidebar(QtWidgets.QWidget):
    """左侧历史栏（可折叠）。"""

    run_selected = QtCore.Signal(str)
    copy_run_id_requested = QtCore.Signal(str, str)
    ask_ai_requested = QtCore.Signal(str, str)

    CONTENT_WIDTH = 200
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
        self._list = ScreenerRunListWidget(mode=mode, main_engine=main_engine, parent=self._content)
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
        self._mode = mode
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
            self.setFixedWidth(self.CONTENT_WIDTH + self.RAIL_WIDTH)
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
