"""AI 选股确认对话框。"""

from __future__ import annotations

from vnpy.event import EventEngine
from vnpy.trader.engine import MainEngine
from vnpy.trader.ui import QtWidgets

from vnpy_ashare.domain.ai_actions import AI_ACTION_FILL_SCREENER, put_ai_action
from vnpy_ashare.app.engine_access import get_screening_service
from vnpy_ashare.app.events import FillScreenerRequest
from vnpy_ashare.screener.data_source import resolve_result_source_tag
from vnpy_ashare.screener.draft_store import cancel_draft, consume_draft, get_draft
from vnpy_ashare.screener.runner import ScreenerRunResult
from vnpy_ashare.ui.workers import ScreenerRunWorker
from vnpy_common.ui.feedback import page_notify
from vnpy_llm.app.engine import LlmEngine


class ScreenerConfirmDialog(QtWidgets.QDialog):
    """展示草案摘要，确认后执行 run_screener。"""

    def __init__(
        self,
        draft_id: str,
        llm_engine: LlmEngine,
        *,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.draft_id = draft_id
        self.llm_engine = llm_engine
        self.main_engine: MainEngine = llm_engine.main_engine
        self.event_engine: EventEngine = llm_engine.event_engine
        self._worker: ScreenerRunWorker | None = None
        self._consumed_draft = None
        self._draft = get_draft(draft_id)

        self.setWindowTitle("确认选股条件")
        self.setMinimumWidth(480)
        self._build_ui()
        self._populate()

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)

        self.intent_label = QtWidgets.QLabel()
        self.intent_label.setWordWrap(True)
        layout.addWidget(QtWidgets.QLabel("用户描述："))
        layout.addWidget(self.intent_label)

        self.summary_label = QtWidgets.QLabel()
        self.summary_label.setWordWrap(True)
        layout.addWidget(QtWidgets.QLabel("解析条件："))
        layout.addWidget(self.summary_label)

        self.source_label = QtWidgets.QLabel()
        layout.addWidget(self.source_label)

        self.warnings_box = QtWidgets.QTextEdit()
        self.warnings_box.setReadOnly(True)
        self.warnings_box.setMaximumHeight(100)
        self.warnings_box.setVisible(False)
        layout.addWidget(self.warnings_box)

        btn_row = QtWidgets.QHBoxLayout()
        self.confirm_btn = QtWidgets.QPushButton("确认运行")
        self.edit_btn = QtWidgets.QPushButton("在策略选股页修改")
        self.cancel_btn = QtWidgets.QPushButton("取消")
        btn_row.addWidget(self.confirm_btn)
        btn_row.addWidget(self.edit_btn)
        btn_row.addStretch()
        btn_row.addWidget(self.cancel_btn)
        layout.addLayout(btn_row)

        self.confirm_btn.clicked.connect(self._on_confirm)
        self.edit_btn.clicked.connect(self._on_edit_in_page)
        self.cancel_btn.clicked.connect(self.reject)

    def _populate(self) -> None:
        draft = self._draft
        if draft is None or draft.status != "pending":
            self.intent_label.setText("草案不存在或已过期，请重新描述选股条件。")
            self.summary_label.setText("")
            self.source_label.setText("")
            self.confirm_btn.setEnabled(False)
            self.edit_btn.setEnabled(False)
            return

        self.intent_label.setText(draft.natural_language or "（无）")
        self.summary_label.setText(draft.summary)
        source_label = resolve_result_source_tag(draft.source)
        self.source_label.setText(f"数据来源：{source_label} · 置信度：{draft.confidence}")

        if draft.warnings:
            self.warnings_box.setVisible(True)
            self.warnings_box.setPlainText("\n".join(f"• {w}" for w in draft.warnings))
        else:
            self.warnings_box.setVisible(False)

    def _on_edit_in_page(self) -> None:
        draft = get_draft(self.draft_id)
        if draft is None or draft.status != "pending":
            page_notify(self, "草案已失效，请重新描述选股条件。", level="warning")
            return
        cancel_draft(self.draft_id)
        put_ai_action(
            self.event_engine,
            AI_ACTION_FILL_SCREENER,
            FillScreenerRequest(
                request=draft.request,
                preset_label=draft.preset_label,
                source_page="AI",
            ),
            action_id="edit_screener_draft",
        )
        self.llm_engine.append_local_message(
            role="assistant",
            content=f"【选股草案】已填入策略选股页「{draft.preset_label}」，请在策略选股页核对后点击「运行策略选股」。",
        )
        self.accept()

    def _on_confirm(self) -> None:
        draft = consume_draft(self.draft_id)
        if draft is None:
            page_notify(self, "草案已过期或已被处理，请重新描述选股条件。", level="warning")
            self.reject()
            return
        self._consumed_draft = draft

        self.confirm_btn.setEnabled(False)
        self.edit_btn.setEnabled(False)
        self.cancel_btn.setEnabled(False)

        req = draft.request
        worker = ScreenerRunWorker(
            preset=req.preset or draft.preset_label,
            top_n=req.top_n,
            min_change_pct=req.min_change_pct,
            max_change_pct=req.max_change_pct,
            min_turnover=req.min_turnover,
            scheme_id=req.scheme_id,
        )
        self._worker = worker
        worker.finished.connect(self._on_run_finished)
        worker.failed.connect(self._on_run_failed)
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        worker.start()

    def _on_run_finished(self, result: ScreenerRunResult) -> None:
        self._worker = None
        draft = self._consumed_draft
        service = get_screening_service(self.main_engine)
        if service is None:
            page_notify(self, "选股服务未就绪", level="warning", title="选股失败")
            self.reject()
            return
        extra_config = service.build_scheme_config(draft.request) if draft else {}
        service.persist_run_result(
            result,
            nl_source=draft.natural_language if draft else "",
            draft_id=self.draft_id if draft else "",
            extra_config=extra_config,
        )
        self.llm_engine.append_local_message(
            role="assistant",
            content=(f"【选股已执行】「{result.condition}」命中 {len(result.rows)} 条，扫描 {result.total_scanned} 只。"),
        )
        self.accept()

    def _on_run_failed(self, message: str) -> None:
        self._worker = None
        page_notify(self, message, level="warning", title="选股失败")
        self.reject()


def show_screener_confirm_dialog(
    draft_id: str,
    llm_engine: LlmEngine,
    *,
    parent: QtWidgets.QWidget | None = None,
) -> None:
    draft = get_draft(draft_id)
    if draft is None or draft.status != "pending":
        return
    dialog = ScreenerConfirmDialog(draft_id, llm_engine, parent=parent)
    dialog.exec()
