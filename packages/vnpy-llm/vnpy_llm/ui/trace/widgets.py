"""对话内嵌折叠 Trace 块。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtGui, QtWidgets

from vnpy_llm.app.engine import LlmEngine
from vnpy_llm.tools.labels import tool_display_name
from vnpy_llm.trace.trace import TraceStep, TurnTrace
from vnpy_llm.ui.themed_styles import bind_ai_trace_style

_STATUS_LABELS = {
    "running": "进行中",
    "ok": "完成",
    "error": "失败",
}


class _ClickableLabel(QtWidgets.QLabel):
    clicked = QtCore.Signal()

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.clicked.emit()
            event.accept()
            return
        super().mousePressEvent(event)


def _step_title(step: TraceStep) -> str:
    if step.kind == "tool":
        return tool_display_name(step.name)
    if step.kind == "routing":
        return "意图路由"
    if step.kind == "reply":
        return "生成回复"
    if step.kind == "error":
        return "错误"
    return step.name


def trace_summary_parts(turn: TurnTrace) -> list[str]:
    parts: list[str] = []
    for step in turn.steps:
        if step.kind == "routing":
            category = step.detail.get("category")
            parts.append(str(category) if category else "意图路由")
        elif step.kind == "tool":
            parts.append(_step_title(step))
        elif step.kind == "reply" and step.status == "running":
            parts.append("生成回复")
        elif step.kind == "error":
            parts.append("错误")
    if not parts and any(step.kind == "reply" for step in turn.steps):
        parts.append("生成回复")
    return parts


def trace_header_text(turn: TurnTrace, *, expanded: bool = False) -> str:
    prefix = "▼" if expanded else "▶"
    status = _STATUS_LABELS.get(turn.status, turn.status)
    parts = trace_summary_parts(turn)
    if parts:
        flow = " → ".join(parts[:5])
        if len(parts) > 5:
            flow += " …"
        return f"{prefix} {flow} · {status}"
    count = len(turn.steps)
    if count:
        return f"{prefix} 执行过程 · {count} 步 · {status}"
    return f"{prefix} 执行过程 · {status}"


def format_step_line(step: TraceStep, index: int) -> str:
    title = _step_title(step)
    if step.status == "running":
        return f"{index}. {title} …"
    mark = "✓" if step.status == "ok" else "✗"
    duration = f" · {step.duration_ms}ms" if step.duration_ms is not None else ""
    return f"{index}. {title} {mark}{duration}"


class AiInlineTraceBlock(QtWidgets.QFrame):
    """单轮对话的可折叠调用链路（默认仅一行摘要）。"""

    def __init__(
        self,
        engine: LlmEngine,
        *,
        turn_id: str = "",
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.engine = engine
        self.turn_id = turn_id
        self._expanded = False
        self._selected_step_id: str | None = None
        self._turn: TurnTrace | None = None
        self.setObjectName("AiInlineTraceBlock")
        bind_ai_trace_style(self)
        self._build_ui()

    def _build_ui(self) -> None:
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(10, 5, 10, 5)
        root.setSpacing(0)

        self._header = _ClickableLabel("▶ 执行过程")
        self._header.setObjectName("AiInlineTraceHeader")
        self._header.setWordWrap(False)
        self._header.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
        self._header.clicked.connect(self._toggle_expanded)
        root.addWidget(self._header)

        self._body = QtWidgets.QWidget()
        body_layout = QtWidgets.QVBoxLayout(self._body)
        body_layout.setContentsMargins(0, 4, 0, 0)
        body_layout.setSpacing(2)

        self._steps_host = QtWidgets.QVBoxLayout()
        self._steps_host.setSpacing(2)
        body_layout.addLayout(self._steps_host)

        self._detail = QtWidgets.QPlainTextEdit()
        self._detail.setObjectName("AiInlineTraceDetail")
        self._detail.setReadOnly(True)
        self._detail.setMaximumBlockCount(2000)
        self._detail.setMaximumHeight(120)
        self._detail.hide()
        body_layout.addWidget(self._detail)

        root.addWidget(self._body)
        self._body.hide()

    def set_expanded(self, expanded: bool) -> None:
        self._expanded = expanded
        self._body.setVisible(expanded)
        if self._turn is not None:
            self._header.setText(trace_header_text(self._turn, expanded=expanded))

    def _toggle_expanded(self) -> None:
        self.set_expanded(not self._expanded)

    def apply_turn(self, turn: TurnTrace, *, expanded: bool | None = None) -> None:
        self.turn_id = turn.turn_id
        self._turn = turn
        if expanded is not None:
            self.set_expanded(expanded)
        else:
            self._header.setText(trace_header_text(turn, expanded=self._expanded))
        self._rebuild_steps(turn)

    def _rebuild_steps(self, turn: TurnTrace) -> None:
        while self._steps_host.count():
            item = self._steps_host.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        for index, step in enumerate(turn.steps, start=1):
            btn = QtWidgets.QPushButton(format_step_line(step, index))
            btn.setObjectName("AiInlineTraceStep")
            btn.setFlat(True)
            btn.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
            btn.setToolTip(step.summary)
            btn.setProperty("stepStatus", step.status)
            btn.style().unpolish(btn)
            btn.style().polish(btn)
            btn.clicked.connect(lambda _checked=False, sid=step.id: self._show_step_detail(sid))
            self._steps_host.addWidget(btn)

        if self._expanded and self._selected_step_id and self.engine.get_trace_step(self._selected_step_id):
            self._show_step_detail(self._selected_step_id)
        else:
            self._detail.hide()

    def _show_step_detail(self, step_id: str) -> None:
        if not self._expanded:
            self.set_expanded(True)
        step = self.engine.get_trace_step(step_id)
        if step is None:
            self._detail.hide()
            return
        self._selected_step_id = step_id
        self._detail.setPlainText(self.engine.format_trace_step_detail(step))
        self._detail.show()

    def sync_width(self, width: int) -> None:
        width = max(220, width)
        self.setMinimumWidth(width)
        self.setMaximumWidth(width)
