"""任务运行输出面板（摘要 + 可滚动日志，选股/本地等页复用）。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_common.ui.theme import theme_manager


class TaskRunOutputPanel(QtWidgets.QWidget):
    """最近一次任务摘要 + 过程日志。"""

    expansion_changed = QtCore.Signal(bool)

    def __init__(
        self,
        parent: QtWidgets.QWidget | None = None,
        *,
        title: str = "运行输出",
        log_placeholder: str = "暂无执行日志",
        object_name: str = "TaskRunOutputPanel",
        section_label_object_name: str = "TaskSectionLabel",
        summary_object_name: str = "TaskRunSummary",
        log_view_object_name: str = "TaskRunLogView",
        expanded: bool = False,
    ) -> None:
        super().__init__(parent)
        self.setObjectName(object_name)
        self._title = title
        self._log_placeholder = log_placeholder
        self._section_label_object_name = section_label_object_name
        self._summary_object_name = summary_object_name
        self._log_view_object_name = log_view_object_name
        self._expanded = expanded
        self._build_ui()
        theme_manager().bind_stylesheet(self)
        self.set_expanded(expanded, emit=False)

    def _build_ui(self) -> None:
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 8, 0, 0)
        root.setSpacing(6)

        header = QtWidgets.QHBoxLayout()
        header.setSpacing(6)
        self._collapse_button = QtWidgets.QToolButton(self)
        self._collapse_button.setCheckable(True)
        self._collapse_button.clicked.connect(self._on_collapse_toggled)
        header.addWidget(self._collapse_button)

        title = QtWidgets.QLabel(self._title)
        title.setObjectName(self._section_label_object_name)
        header.addWidget(title)
        header.addStretch()
        root.addLayout(header)

        self._summary_label = QtWidgets.QLabel("")
        self._summary_label.setObjectName(self._summary_object_name)
        self._summary_label.setWordWrap(True)
        root.addWidget(self._summary_label)

        self._log_view = QtWidgets.QPlainTextEdit()
        self._log_view.setObjectName(self._log_view_object_name)
        self._log_view.setReadOnly(True)
        self._log_view.setLineWrapMode(QtWidgets.QPlainTextEdit.LineWrapMode.WidgetWidth)
        self._log_view.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._log_view.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._log_view.setPlaceholderText(self._log_placeholder)
        root.addWidget(self._log_view, stretch=1)

    def is_expanded(self) -> bool:
        return self._expanded

    def set_expanded(self, expanded: bool, *, emit: bool = True) -> None:
        changed = self._expanded != expanded
        self._expanded = expanded
        self._sync_collapse_button()
        self._summary_label.setVisible(expanded and bool(self._summary_label.text()))
        self._log_view.setVisible(expanded)
        if expanded:
            self.setMaximumHeight(16777215)
            self.setMinimumHeight(120)
        else:
            self.setMinimumHeight(28)
            self.setMaximumHeight(36)
        if emit and changed:
            self.expansion_changed.emit(expanded)

    def expand(self) -> None:
        self.set_expanded(True)

    def collapse(self) -> None:
        self.set_expanded(False)

    def _sync_collapse_button(self) -> None:
        self._collapse_button.blockSignals(True)
        self._collapse_button.setChecked(self._expanded)
        self._collapse_button.setArrowType(QtCore.Qt.ArrowType.DownArrow if self._expanded else QtCore.Qt.ArrowType.RightArrow)
        self._collapse_button.blockSignals(False)

    def _on_collapse_toggled(self, expanded: bool) -> None:
        self.set_expanded(expanded)

    def _show_summary(self, text: str) -> None:
        self._summary_label.setText(text)
        if self._expanded:
            self._summary_label.setVisible(bool(text))

    def set_summary(self, text: str) -> None:
        self._show_summary(text)

    def append_log(self, message: str) -> None:
        text = str(message).strip()
        if not text:
            return
        self._log_view.appendPlainText(text)
        scrollbar = self._log_view.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def clear_log(self) -> None:
        self._log_view.clear()

    def begin_task(self, title: str) -> None:
        self._show_summary("正在执行…")
        self.clear_log()
        self.append_log(f"[开始] {title}")

    def complete_task(self, *, summary: str, detail: str | None = None) -> None:
        self._show_summary(summary)
        self.append_log("[完成]")
        if detail:
            self.append_log(detail)

    def fail_task(self, message: str) -> None:
        self._show_summary("运行失败")
        self.append_log(f"[错误] {message}")

    def begin_run(self, *, label: str, top_n: int, kind: str = "方案") -> None:
        self.begin_task(f"{kind}：{label} · Top {top_n}")

    def complete_run(self, *, summary: str, detail: str | None = None) -> None:
        self.complete_task(summary=summary, detail=detail)

    def fail_run(self, message: str) -> None:
        self.fail_task(message)

    def load_history(self, *, summary: str, log_tag: str = "历史") -> None:
        self._show_summary(summary)
        self.append_log(f"[{log_tag}] 已载入")
