"""策略选股运行输出面板（摘要 + 日志）。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.ui.styles import TERMINAL_STYLESHEET


class ScreenerRunOutputPanel(QtWidgets.QWidget):
    """左栏下半区：最近一次运行摘要 + 过程日志。"""

    def __init__(
        self,
        parent: QtWidgets.QWidget | None = None,
        *,
        log_placeholder: str = "暂无日志",
    ) -> None:
        super().__init__(parent)
        self.setObjectName("ScreenerRunOutputPanel")
        self.setStyleSheet(TERMINAL_STYLESHEET)
        self._log_placeholder = log_placeholder
        self._build_ui()

    def _build_ui(self) -> None:
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 8, 0, 0)
        root.setSpacing(6)

        title = QtWidgets.QLabel("运行输出")
        title.setObjectName("ScreenerSectionLabel")
        root.addWidget(title)

        self._summary_label = QtWidgets.QLabel("")
        self._summary_label.setObjectName("ScreenerRunSummary")
        self._summary_label.setWordWrap(True)
        self._summary_label.hide()
        root.addWidget(self._summary_label)

        self._log_view = QtWidgets.QPlainTextEdit()
        self._log_view.setObjectName("ScreenerRunLogView")
        self._log_view.setReadOnly(True)
        self._log_view.setLineWrapMode(QtWidgets.QPlainTextEdit.LineWrapMode.WidgetWidth)
        self._log_view.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._log_view.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._log_view.setPlaceholderText(self._log_placeholder)
        root.addWidget(self._log_view, stretch=1)

    def _show_summary(self, text: str) -> None:
        self._summary_label.setText(text)
        self._summary_label.setVisible(bool(text))

    def set_summary(self, text: str) -> None:
        self._show_summary(text)

    def append_log(self, message: str) -> None:
        self._log_view.appendPlainText(message)
        scrollbar = self._log_view.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def clear_log(self) -> None:
        self._log_view.clear()

    def begin_run(self, *, label: str, top_n: int, kind: str = "方案") -> None:
        self._show_summary("正在执行…")
        self.clear_log()
        self.append_log(f"[开始] {kind}：{label} · Top {top_n}")

    def complete_run(self, *, summary: str, detail: str | None = None) -> None:
        self._show_summary(summary)
        self.append_log("[完成]")
        if detail:
            self.append_log(detail)

    def fail_run(self, message: str) -> None:
        self._show_summary("运行失败")
        self.append_log(f"[错误] {message}")

    def load_history(self, *, summary: str, log_tag: str = "历史") -> None:
        self._show_summary(summary)
        self.append_log(f"[{log_tag}] 已载入")
