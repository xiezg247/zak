"""自动选股页：多因子配方 + 定时/AI 结果收件箱。"""

from __future__ import annotations

from typing import Any

from vnpy.event import Event, EventEngine
from vnpy.trader.engine import MainEngine
from vnpy.trader.ui import QtCore, QtGui, QtWidgets

from vnpy_ashare.ai.screener_context import build_ask_ai_prompt_for_run, sync_screener_page_context
from vnpy_ashare.ai.symbol import parse_stock_symbol
from vnpy_ashare.app.engine_access import (
    get_backtest_service,
    get_screening_service,
    get_watchlist_service,
)
from vnpy_ashare.app.events import (
    EVENT_ASK_AI,
    EVENT_OPEN_BACKTEST,
    EVENT_ORB_ATTENTION,
    AskAiRequest,
    BacktestRequest,
    OrbAttentionRequest,
)
from vnpy_ashare.screener.runner import ScreenerRunResult
from vnpy_ashare.services.screening_service import ScreeningService
from vnpy_ashare.ui.backtest.batch_backtest_flow import BatchBacktestFlow
from vnpy_ashare.ui.screener.screener_recipe_panel import ScreenerRecipePanel
from vnpy_ashare.ui.screener.screener_results_table import (
    apply_screener_results_view,
    configure_screener_results_table,
    iter_checked_table_rows,
    select_all_table_rows,
)
from vnpy_ashare.ui.screener.screener_run_output_panel import ScreenerRunOutputPanel
from vnpy_ashare.ui.screener.screener_run_sidebar import ScreenerRunSidebar
from vnpy_ashare.ui.workers import ScreenerBatchDownloadWorker, ScreenerRecipeRunWorker
from vnpy_common.ui.feedback import PageToastHost, TaskGuard
from vnpy_common.ui.qt_helpers import release_thread


class AutoScreenerPageWidget(QtWidgets.QWidget):
    """左侧导航「自动选股」页。"""

    open_scheduler_requested = QtCore.Signal()

    def __init__(self, main_engine: MainEngine, event_engine: EventEngine) -> None:
        super().__init__()
        self.main_engine = main_engine
        self.event_engine = event_engine
        self.setObjectName("MarketRoot")
        self._recipe_worker: ScreenerRecipeRunWorker | None = None
        self._download_worker: ScreenerBatchDownloadWorker | None = None
        self._batch_backtest_flow: BatchBacktestFlow | None = None
        self._retired_workers: list[QtCore.QThread] = []
        self._results: list[dict[str, Any]] = []
        self._result_columns: list[tuple[str, str]] = []
        self._loaded_run_id: str | None = None
        self._watchlist_service = get_watchlist_service(main_engine)
        self._active = False

        self._build_ui()
        self._task_guard = TaskGuard(self._toast)
        self._batch_backtest_flow = BatchBacktestFlow(
            main_engine=main_engine,
            event_engine=event_engine,
            parent=self,
            on_status=self._append_action_log,
        )

    def _screening_service(self) -> ScreeningService | None:
        return get_screening_service(self.main_engine)

    def _build_ui(self) -> None:
        page_layout = QtWidgets.QHBoxLayout(self)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(0)

        self.run_sidebar = ScreenerRunSidebar(mode="auto", main_engine=self.main_engine, parent=self)
        self.run_sidebar.run_selected.connect(self._load_historical_run)
        self.run_sidebar.copy_run_id_requested.connect(self._on_copy_run_id)
        self.run_sidebar.ask_ai_requested.connect(self._on_ask_ai_for_run)
        self.run_sidebar.runs_deleted.connect(self._on_runs_deleted)
        page_layout.addWidget(self.run_sidebar)

        main_panel = QtWidgets.QWidget()
        root = QtWidgets.QVBoxLayout(main_panel)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(0)
        page_layout.addWidget(main_panel, stretch=1)

        header = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("自动选股")
        title.setObjectName("PageTitle")
        header.addWidget(title)
        header.addStretch()
        self.scheduler_btn = QtWidgets.QPushButton("定时任务设置")
        self.scheduler_btn.setObjectName("SecondaryButton")
        self.scheduler_btn.clicked.connect(self.open_scheduler_requested.emit)
        header.addWidget(self.scheduler_btn)
        root.addLayout(header)

        toolbar = QtWidgets.QHBoxLayout()
        toolbar.setContentsMargins(0, 8, 0, 8)
        toolbar.setSpacing(8)

        self.select_all_btn = QtWidgets.QPushButton("全 选")
        self.select_all_btn.setObjectName("SecondaryButton")
        self.select_all_btn.clicked.connect(lambda: select_all_table_rows(self.result_table))
        toolbar.addWidget(self.select_all_btn)

        self.add_watchlist_btn = QtWidgets.QPushButton("加入自选")
        self.add_watchlist_btn.setObjectName("SecondaryButton")
        self.add_watchlist_btn.clicked.connect(self._add_selected_to_watchlist)
        toolbar.addWidget(self.add_watchlist_btn)

        self.download_btn = QtWidgets.QPushButton("下载日K")
        self.download_btn.setObjectName("SecondaryButton")
        self.download_btn.clicked.connect(self._download_selected_bars)
        toolbar.addWidget(self.download_btn)

        self.backtest_btn = QtWidgets.QPushButton("策略回测")
        self.backtest_btn.setObjectName("SecondaryButton")
        self.backtest_btn.clicked.connect(self._open_backtest_for_selection)
        toolbar.addWidget(self.backtest_btn)

        self.batch_backtest_btn = QtWidgets.QPushButton("批量回测")
        self.batch_backtest_btn.setObjectName("SecondaryButton")
        self.batch_backtest_btn.clicked.connect(self._run_batch_backtest)
        toolbar.addWidget(self.batch_backtest_btn)

        self.export_btn = QtWidgets.QPushButton("CSV")
        self.export_btn.setObjectName("SecondaryButton")
        self.export_btn.clicked.connect(self._export_csv)
        toolbar.addWidget(self.export_btn)
        toolbar.addStretch()
        root.addLayout(toolbar)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(1)

        left_column = QtWidgets.QWidget()
        left_column_layout = QtWidgets.QVBoxLayout(left_column)
        left_column_layout.setContentsMargins(0, 0, 10, 0)
        left_column_layout.setSpacing(0)

        left_splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        left_splitter.setChildrenCollapsible(False)
        left_splitter.setHandleWidth(1)

        form_panel = QtWidgets.QWidget()
        form_panel.setObjectName("ScreenerFormPanel")
        form_layout = QtWidgets.QVBoxLayout(form_panel)
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.setSpacing(6)

        hint = QtWidgets.QLabel("在此配置多因子配方；定时任务仅引用配方 ID 与 Cron。盘中/盘后任务完成后，结果会出现在左侧自动结果列表。")
        hint.setObjectName("ScreenerHint")
        hint.setWordWrap(True)
        form_layout.addWidget(hint)

        self.recipe_panel = ScreenerRecipePanel(parent=form_panel)
        self.recipe_panel.run_requested.connect(self._run_recipe)
        form_layout.addWidget(self.recipe_panel)
        form_layout.addStretch()
        left_splitter.addWidget(form_panel)

        self.run_output_panel = ScreenerRunOutputPanel(parent=left_column)
        left_splitter.addWidget(self.run_output_panel)
        left_splitter.setStretchFactor(0, 1)
        left_splitter.setStretchFactor(1, 1)
        left_splitter.setSizes([280, 280])

        left_column_layout.addWidget(left_splitter)
        splitter.addWidget(left_column)

        result_panel = QtWidgets.QWidget()
        result_layout = QtWidgets.QVBoxLayout(result_panel)
        result_layout.setContentsMargins(4, 0, 0, 0)
        result_layout.setSpacing(0)

        result_body = QtWidgets.QWidget()
        result_body_layout = QtWidgets.QVBoxLayout(result_body)
        result_body_layout.setContentsMargins(0, 0, 0, 0)
        result_body_layout.setSpacing(0)

        self._empty_result_label = QtWidgets.QLabel("试跑配方或选择左侧自动结果后在此展示")
        self._empty_result_label.setObjectName("ScreenerEmptyResult")
        self._empty_result_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        result_body_layout.addWidget(self._empty_result_label, stretch=1)

        self.result_table = QtWidgets.QTableWidget(0, 0)
        self.result_table.setObjectName("MarketTable")
        configure_screener_results_table(self.result_table)
        self.result_table.hide()
        result_body_layout.addWidget(self.result_table, stretch=1)
        result_layout.addWidget(result_body, stretch=1)
        splitter.addWidget(result_panel)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([300, 700])
        root.addWidget(splitter, stretch=1)

        self._toast = PageToastHost(main_panel)
        root.addWidget(self._toast)

    def _task_lock_widgets(self) -> list[QtWidgets.QWidget]:
        return [
            self.scheduler_btn,
            self.select_all_btn,
            self.add_watchlist_btn,
            self.download_btn,
            self.backtest_btn,
            self.batch_backtest_btn,
            self.export_btn,
            *self.recipe_panel.task_lock_widgets(),
        ]

    def _append_action_log(self, message: str) -> None:
        if message:
            self.run_output_panel.append_log(message)

    def _release_worker(
        self,
        worker: QtCore.QThread | None,
        *,
        timeout_ms: int = 3000,
    ) -> None:
        release_thread(self._retired_workers, worker, timeout_ms=timeout_ms)

    def _run_recipe(self, recipe, recipe_id: str) -> None:
        if self._task_guard.active:
            return
        if self._recipe_worker is not None and self._recipe_worker.isRunning():
            return
        label = str(getattr(recipe, "name", recipe_id) or recipe_id)
        top_n = int(getattr(recipe, "top_n", 20) or 20)
        self._task_guard.begin(
            f"正在试跑配方「{label}」…",
            widgets=self._task_lock_widgets(),
            primary=self.recipe_panel._run_btn,
            primary_text="试跑配方",
            primary_handler=self.recipe_panel._run_recipe,
            on_cancel=self._cancel_recipe,
        )
        self.run_output_panel.begin_run(label=label, top_n=top_n, kind="配方")
        worker = ScreenerRecipeRunWorker(recipe, recipe_id)
        self._recipe_worker = worker
        worker.finished.connect(self._on_recipe_finished)
        worker.failed.connect(self._on_recipe_failed)
        worker.start()

    def _cancel_recipe(self) -> None:
        if self._recipe_worker is not None:
            self._recipe_worker.request_cancel()

    def _on_recipe_finished(self, result: ScreenerRunResult, recipe_id: str) -> None:
        worker = self._recipe_worker
        self._recipe_worker = None
        self._release_worker(worker)
        if not self._active:
            self._task_guard.end()
            return
        cancelled = self._task_guard.cancelled
        self._task_guard.end()
        if cancelled:
            self.run_output_panel.fail_run("已取消")
            self._toast.info("配方试跑已取消")
            return
        summary = self._apply_result(result)
        service = self._screening_service()
        if service is not None:
            service.persist_run_result(
                result,
                extra_config={"trigger": "manual", "recipe_id": recipe_id},
            )
        else:
            self._store_screening_results(
                condition=result.condition,
                rows=self._results,
                updated_at=result.updated_at,
            )
        self.run_output_panel.complete_run(
            summary=summary,
            detail=f"配方 ID {recipe_id} · 已写入自动结果",
        )
        self.run_sidebar.refresh()
        sync_screener_page_context(self.main_engine)
        self._toast.success(f"配方试跑完成，命中 {len(self._results)} 条")

    def _on_recipe_failed(self, message: str) -> None:
        worker = self._recipe_worker
        self._recipe_worker = None
        self._release_worker(worker)
        if not self._active:
            self._task_guard.end()
            return
        cancelled = self._task_guard.cancelled
        self._task_guard.end()
        if cancelled or message == "已取消":
            self.run_output_panel.fail_run("已取消")
            self._toast.info("配方试跑已取消")
            return
        self.run_output_panel.fail_run(message)
        self._toast.error(message)

    def _format_result_summary(
        self,
        *,
        condition: str,
        row_count: int,
        total_scanned: int,
        source: str,
        updated_at: str | None,
        prefix: str = "",
    ) -> str:
        service = self._screening_service()
        source_label = service.format_source_tag(source) if service else source
        updated = updated_at or "-"
        headline = f"「{condition}」命中 {row_count} 条 · 扫描 {total_scanned} 只 · {source_label} · 更新 {updated}"
        return f"{prefix}{headline}" if prefix else headline

    def _apply_result(self, result: ScreenerRunResult, *, prefix: str = "") -> str:
        service = self._screening_service()
        self._results = list(result.rows)
        self._result_columns = result.columns or (service.resolve_export_columns(self._results) if service else [])
        apply_screener_results_view(
            self.result_table,
            self._results,
            self._result_columns,
            empty_label=self._empty_result_label,
        )
        self._store_screening_results(
            condition=result.condition,
            rows=self._results,
            updated_at=result.updated_at,
        )
        return self._format_result_summary(
            condition=result.condition,
            row_count=len(self._results),
            total_scanned=result.total_scanned,
            source=result.source,
            updated_at=result.updated_at,
            prefix=prefix,
        )

    def on_scheduled_run_complete(self, job_id: str, message: str) -> None:
        self.run_sidebar.refresh()
        self.run_sidebar.set_expanded(True)
        service = self._screening_service()
        latest = service.find_latest_auto_run_for_job(job_id) if service else None
        if latest is not None:
            self._load_historical_run(latest.id, from_scheduler=True)
        self.run_output_panel.append_log(f"[定时] {message}")
        if self.event_engine is not None:
            self.event_engine.put(
                Event(EVENT_ORB_ATTENTION, OrbAttentionRequest(source="auto_screener")),
            )

    def _load_historical_run(self, run_id: str, *, from_scheduler: bool = False) -> None:
        service = self._screening_service()
        record = service.get_run_record(run_id) if service else None
        if record is None:
            self._append_action_log("自动选股结果不存在或已删除")
            self._clear_loaded_run_view()
            return
        self._loaded_run_id = run_id
        if service is not None:
            service.mark_run_read(run_id)
        self._results = list(record.rows)
        self._result_columns = service.resolve_export_columns(self._results) if service else []
        apply_screener_results_view(
            self.result_table,
            self._results,
            self._result_columns,
            empty_label=self._empty_result_label,
        )
        self._store_screening_results(
            condition=record.condition,
            rows=self._results,
            updated_at=record.created_at,
        )
        trigger = str(record.config.get("trigger", ""))
        prefix = ""
        if trigger.startswith("scheduled_"):
            reason = record.config.get("reason_summary") or trigger.removeprefix("scheduled_")
            prefix = f"自动 · {reason} · "
        elif record.config.get("recipe_id"):
            prefix = "配方试跑 · "
        summary = self._format_result_summary(
            condition=record.condition,
            row_count=len(self._results),
            total_scanned=record.total_scanned,
            source=record.source,
            updated_at=record.created_at,
            prefix=prefix,
        )
        log_tag = "定时" if from_scheduler else "历史"
        self.run_output_panel.load_history(summary=summary, log_tag=log_tag)
        self.run_sidebar.refresh()
        sync_screener_page_context(self.main_engine)

    def _clear_loaded_run_view(self) -> None:
        self._loaded_run_id = None
        self._results = []
        self._result_columns = []
        apply_screener_results_view(
            self.result_table,
            self._results,
            self._result_columns,
            empty_label=self._empty_result_label,
        )
        self._store_screening_results(condition="", rows=[])

    def _on_runs_deleted(self, run_ids: list) -> None:
        if self._loaded_run_id is not None and self._loaded_run_id in run_ids:
            self._clear_loaded_run_view()
            self._append_action_log("已删除当前展示的自动结果")

    def _on_copy_run_id(self, run_id: str, condition: str) -> None:
        short = run_id[:8] + "…" if len(run_id) > 8 else run_id
        self._append_action_log(f"已复制 run_id（{condition}）：{short}")

    def _on_ask_ai_for_run(self, run_id: str, condition: str) -> None:
        if self.event_engine is None:
            return
        prompt = build_ask_ai_prompt_for_run(run_id, condition)
        self.event_engine.put(
            Event(
                EVENT_ASK_AI,
                AskAiRequest(prompt=prompt, source_page="自动选股"),
            )
        )
        self._append_action_log(f"已打开 AI，预填解读请求：{condition}")

    def _store_screening_results(self, *, condition: str, rows: list, updated_at: str | None = None) -> None:
        service = self._screening_service()
        if service is not None:
            service.set_screening_results(condition=condition, rows=rows, updated_at=updated_at)

    def _add_selected_to_watchlist(self) -> None:
        if self._watchlist_service is None:
            self._toast.warning("自选服务未就绪")
            return
        selected = iter_checked_table_rows(self.result_table)
        if not selected:
            self._toast.warning("请先勾选要加入自选的标的")
            return
        added = skipped = 0
        for row in selected:
            item = parse_stock_symbol(str(row.get("vt_symbol", "")))
            if item is None:
                skipped += 1
                continue
            name = str(row.get("name", "") or item.name)
            if self._watchlist_service.add(item.symbol, item.exchange, name):
                added += 1
            else:
                skipped += 1
        msg = f"新加入 {added} 只"
        if skipped:
            msg += f" · 跳过 {skipped} 只"
        self._append_action_log(msg)
        self._toast.success(msg)

    def _download_selected_bars(self) -> None:
        if self._task_guard.active:
            return
        if self._download_worker is not None and self._download_worker.isRunning():
            return
        selected = iter_checked_table_rows(self.result_table)
        if not selected:
            self._toast.warning("请先勾选要下载日 K 的标的")
            return
        self._task_guard.begin(
            f"正在下载 {len(selected)} 只日 K…",
            widgets=self._task_lock_widgets(),
            primary=self.download_btn,
            primary_text="下载日K",
            primary_handler=self._download_selected_bars,
            on_cancel=self._cancel_download,
        )
        self._append_action_log(f"正在下载 {len(selected)} 只日 K…")
        worker = ScreenerBatchDownloadWorker(selected)
        self._download_worker = worker
        worker.finished.connect(self._on_download_finished)
        worker.failed.connect(self._on_download_failed)
        worker.start()

    def _cancel_download(self) -> None:
        if self._download_worker is not None:
            self._download_worker.request_cancel()

    def _on_download_finished(self, result) -> None:
        worker = self._download_worker
        self._download_worker = None
        self._release_worker(worker)
        if not self._active:
            self._task_guard.end()
            return
        cancelled = self._task_guard.cancelled
        self._task_guard.end()
        message = getattr(result, "message", str(result))
        if cancelled or "已取消" in message:
            self._append_action_log("日 K 下载已取消")
            self._toast.info("日 K 下载已取消")
            return
        self._append_action_log(message)
        if getattr(result, "success", True):
            self._toast.success(message)
        else:
            self._toast.error(message)

    def _on_download_failed(self, message: str) -> None:
        worker = self._download_worker
        self._download_worker = None
        self._release_worker(worker)
        if not self._active:
            self._task_guard.end()
            return
        cancelled = self._task_guard.cancelled
        self._task_guard.end()
        if cancelled or message == "已取消":
            self._append_action_log("日 K 下载已取消")
            self._toast.info("日 K 下载已取消")
            return
        self._append_action_log(message)
        self._toast.error(message)

    def _open_backtest_for_selection(self) -> None:
        selected = iter_checked_table_rows(self.result_table)
        if not selected:
            self._toast.warning("请先勾选一只标的进行回测")
            return
        if len(selected) > 1:
            self._toast.info("「策略回测」仅打开单只；批量请用「批量回测」")
            return
        row = selected[0]
        vt_symbol = str(row.get("vt_symbol", ""))
        if not vt_symbol:
            return
        self.event_engine.put(
            Event(
                EVENT_OPEN_BACKTEST,
                BacktestRequest(vt_symbol=vt_symbol, source_page="自动选股", name=str(row.get("name", ""))),
            )
        )

    def _run_batch_backtest(self) -> None:
        if self._batch_backtest_flow is not None and self._batch_backtest_flow.is_running():
            return
        selected = iter_checked_table_rows(self.result_table)
        if not selected:
            self._toast.warning("请先勾选要批量回测的标的")
            return
        backtest_service = get_backtest_service(self.main_engine)
        strategies = backtest_service.list_strategies() if backtest_service else []
        class_names = [item["class_name"] for item in strategies if item.get("class_name")]
        self._batch_backtest_flow.start(
            selected,
            source_page="自动选股",
            batch_source="batch_auto_screener",
            list_strategies=lambda: class_names,
            on_running=lambda running: self.batch_backtest_btn.setDisabled(running),
        )

    def _export_csv(self) -> None:
        if not self._results:
            self._toast.warning("暂无自动选股结果")
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "导出 CSV",
            "auto_screener_results.csv",
            "CSV (*.csv)",
        )
        if not path:
            return
        if not path.lower().endswith(".csv"):
            path += ".csv"
        service = self._screening_service()
        if service is not None:
            service.export_csv(self._results, path)
        self._append_action_log(f"已导出：{path}")
        self._toast.success(f"已导出 CSV：{path}")

    def activate(self) -> None:
        self._active = True
        self.recipe_panel.reload()
        self.run_sidebar.refresh()
        sync_screener_page_context(self.main_engine)

    def deactivate(self) -> None:
        self._active = False
        if self._recipe_worker is not None:
            self._recipe_worker.request_cancel()
        if self._download_worker is not None:
            self._download_worker.request_cancel()
        self._task_guard.end()
        for attr in ("_recipe_worker", "_download_worker"):
            worker = getattr(self, attr, None)
            setattr(self, attr, None)
            self._release_worker(worker, timeout_ms=0)
        if self._batch_backtest_flow is not None:
            self._batch_backtest_flow.release_worker(self._retired_workers, timeout_ms=0)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        self.deactivate()
        super().closeEvent(event)
