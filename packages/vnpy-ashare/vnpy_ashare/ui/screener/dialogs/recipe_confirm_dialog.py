"""AI 多因子配方确认对话框。"""

from __future__ import annotations

from vnpy.event import EventEngine
from vnpy.trader.engine import MainEngine
from vnpy.trader.ui import QtWidgets

from vnpy_ashare.app.engine_access import get_screening_service
from vnpy_ashare.app.events import FillRecipeRequest
from vnpy_ashare.domain.ai_actions import AI_ACTION_FILL_RECIPE, put_ai_action
from vnpy_ashare.screener.recipe.recipe import resolve_recipe
from vnpy_ashare.screener.recipe.recipe_draft_store import cancel_recipe_draft, consume_recipe_draft, get_recipe_draft
from vnpy_ashare.screener.run.runner import ScreenerRunResult
from vnpy_ashare.ui.screener.workers import ScreenerRecipeRunWorker
from vnpy_common.ui.feedback import page_notify
from vnpy_llm.app.engine import LlmEngine


class RecipeConfirmDialog(QtWidgets.QDialog):
    """展示配方草案摘要，确认后执行 run_recipe。"""

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
        self._worker: ScreenerRecipeRunWorker | None = None
        self._consumed_draft = None
        self._draft = get_recipe_draft(draft_id)

        self.setWindowTitle("确认多因子配方")
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
        layout.addWidget(QtWidgets.QLabel("配方摘要："))
        layout.addWidget(self.summary_label)

        self.meta_label = QtWidgets.QLabel()
        layout.addWidget(self.meta_label)

        btn_row = QtWidgets.QHBoxLayout()
        self.confirm_btn = QtWidgets.QPushButton("确认运行")
        self.edit_btn = QtWidgets.QPushButton("在自动选股页修改")
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
            self.intent_label.setText("草案不存在或已过期，请重新描述多因子选股条件。")
            self.summary_label.setText("")
            self.meta_label.setText("")
            self.confirm_btn.setEnabled(False)
            self.edit_btn.setEnabled(False)
            return

        self.intent_label.setText(draft.natural_language or "（无）")
        self.summary_label.setText(draft.summary)
        trigger_label = "盘中" if draft.trigger_kind == "intraday" else "盘后"
        self.meta_label.setText(f"触发类型：{trigger_label} · 配方 ID：{draft.recipe_id} · Top {draft.top_n} · 置信度：{draft.confidence}")

    def _on_edit_in_page(self) -> None:
        draft = get_recipe_draft(self.draft_id)
        if draft is None or draft.status != "pending":
            page_notify(self, "草案已失效，请重新描述多因子选股条件。", level="warning")
            return
        cancel_recipe_draft(self.draft_id)
        put_ai_action(
            self.event_engine,
            AI_ACTION_FILL_RECIPE,
            FillRecipeRequest(
                recipe_id=draft.recipe_id,
                trigger_kind=draft.trigger_kind,
                top_n=draft.top_n,
                source_page="AI",
            ),
            action_id="edit_recipe_draft",
        )
        self.llm_engine.append_local_message(
            role="assistant",
            content=(f"【配方草案】已跳转自动选股页并选中「{draft.summary}」，请核对维度权重后点击「试跑配方」或配置定时任务。"),
        )
        self.accept()

    def _on_confirm(self) -> None:
        draft = consume_recipe_draft(self.draft_id)
        if draft is None:
            page_notify(self, "草案已过期或已被处理，请重新描述多因子选股条件。", level="warning")
            self.reject()
            return
        self._consumed_draft = draft
        recipe = resolve_recipe(draft.recipe_id)
        if recipe is None:
            page_notify(self, f"未知配方：{draft.recipe_id}", level="warning", title="配方失败")
            self.reject()
            return

        self.confirm_btn.setEnabled(False)
        self.edit_btn.setEnabled(False)
        self.cancel_btn.setEnabled(False)

        worker = ScreenerRecipeRunWorker(
            recipe,
            draft.recipe_id,
            top_n=draft.top_n,
            condition_prefix="AI",
        )
        self._worker = worker
        worker.finished.connect(self._on_run_finished)
        worker.failed.connect(self._on_run_failed)
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        worker.start()

    def _on_run_finished(self, result: ScreenerRunResult, recipe_id: str) -> None:
        self._worker = None
        draft = self._consumed_draft
        service = get_screening_service(self.main_engine)
        if service is None:
            page_notify(self, "选股服务未就绪", level="warning", title="配方失败")
            self.reject()
            return
        service.persist_run_result(
            result,
            nl_source=draft.natural_language if draft else "",
            draft_id=self.draft_id if draft else "",
            extra_config={"trigger": "ai_recipe", "recipe_id": recipe_id},
        )
        self.llm_engine.append_local_message(
            role="assistant",
            content=(f"【配方已执行】「{result.condition}」命中 {len(result.rows)} 条，扫描 {result.total_scanned} 只。"),
        )
        self.accept()

    def _on_run_failed(self, message: str) -> None:
        self._worker = None
        page_notify(self, message, level="warning", title="配方失败")
        self.reject()


def show_recipe_confirm_dialog(
    draft_id: str,
    llm_engine: LlmEngine,
    *,
    parent: QtWidgets.QWidget | None = None,
) -> None:
    draft = get_recipe_draft(draft_id)
    if draft is None or draft.status != "pending":
        return
    dialog = RecipeConfirmDialog(draft_id, llm_engine, parent=parent)
    dialog.exec()
