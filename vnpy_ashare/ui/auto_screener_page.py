"""自动选股页：多因子配方 + 定时/AI 结果收件箱。"""

from __future__ import annotations

from typing import Any

from vnpy.event import Event, EventEngine

from vnpy_ashare.events import (
    EVENT_ASK_AI,
    EVENT_OPEN_BACKTEST,
    EVENT_ORB_ATTENTION,
    AskAiRequest,
    BacktestRequest,
    OrbAttentionRequest,
)
from vnpy.trader.engine import MainEngine
from vnpy.trader.ui import QtCore, QtGui, QtWidgets

from vnpy_ashare.ai.screener_context import build_ask_ai_prompt_for_run, sync_screener_page_context
from vnpy_ashare.ai.symbol import parse_stock_symbol
from vnpy_ashare.engine import APP_NAME, AshareEngine
from vnpy_ashare.screener.data_source import resolve_result_source_tag
from vnpy_ashare.screener.export import export_rows_to_csv, resolve_export_columns
from vnpy_ashare.screener.runner import ScreenerRunResult
from vnpy_ashare.screener.run_store import get_run, mark_run_read, save_run
from vnpy_ashare.ui.batch_backtest_flow import BatchBacktestFlow
from vnpy_ashare.ui.qt_helpers import release_thread
from vnpy_ashare.ui.screener_recipe_panel import ScreenerRecipePanel
from vnpy_ashare.ui.screener_results_table import (
    iter_checked_table_rows,
    populate_screener_results_table,
    select_all_table_rows,
)
from vnpy_ashare.ui.screener_run_sidebar import ScreenerRunSidebar
from vnpy_ashare.ui.styles import TERMINAL_STYLESHEET
from vnpy_ashare.ui.worker import ScreenerBatchDownloadWorker, ScreenerRecipeRunWorker


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
        self._batch_backtest_flow = BatchBacktestFlow(
            main_engine=main_engine,
            event_engine=event_engine,
            parent=self,
            on_status=lambda message: self._status_label.setText(message),
        )
        self._retired_workers: list[QtCore.QThread] = []
        self._results: list[dict[str, Any]] = []
        self._result_columns: list[tuple[str, str]] = []
        self._watchlist_service = self._get_watchlist_service()

        self._build_ui()
        self.setStyleSheet(TERMINAL_STYLESHEET)

    def _get_watchlist_service(self):
        engine = self.main_engine.get_engine(APP_NAME)
        if isinstance(engine, AshareEngine):
            return engine.watchlist_service
        return None

    def _build_ui(self) -> None:
        page_layout = QtWidgets.QHBoxLayout(self)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(0)

        self.run_sidebar = ScreenerRunSidebar(mode="auto", parent=self)
        self.run_sidebar.run_selected.connect(self._load_historical_run)
        self.run_sidebar.copy_run_id_requested.connect(self._on_copy_run_id)
        self.run_sidebar.ask_ai_requested.connect(self._on_ask_ai_for_run)
        page_layout.addWidget(self.run_sidebar)

        main_panel = QtWidgets.QWidget()
        root = QtWidgets.QVBoxLayout(main_panel)
        root.setContentsMargins(16, 12, 16, 0)
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

        form_panel = QtWidgets.QWidget()
        form_panel.setObjectName("ScreenerFormPanel")
        form_layout = QtWidgets.QVBoxLayout(form_panel)
        form_layout.setContentsMargins(0, 0, 10, 0)
        form_layout.setSpacing(6)

        hint = QtWidgets.QLabel(
            "在此配置多因子配方；定时任务仅引用配方 ID 与 Cron。"
            "盘中/盘后任务完成后，结果会出现在左侧自动结果列表。"
        )
        hint.setObjectName("ScreenerHint")
        hint.setWordWrap(True)
        form_layout.addWidget(hint)

        self.recipe_panel = ScreenerRecipePanel(parent=form_panel)
        self.recipe_panel.run_requested.connect(self._run_recipe)
        form_layout.addWidget(self.recipe_panel)
        form_layout.addStretch()
        splitter.addWidget(form_panel)

        result_panel = QtWidgets.QWidget()
        result_layout = QtWidgets.QVBoxLayout(result_panel)
        result_layout.setContentsMargins(4, 0, 0, 0)
        result_layout.setSpacing(4)

        self._summary_label = QtWidgets.QLabel("")
        self._summary_label.setObjectName("ResultSummary")
        result_layout.addWidget(self._summary_label)

        self.result_table = QtWidgets.QTableWidget(0, 1)
        self.result_table.setObjectName("MarketTable")
        self.result_table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.result_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.result_table.verticalHeader().setVisible(False)
        self.result_table.setAlternatingRowColors(True)
        result_layout.addWidget(self.result_table, stretch=1)
        splitter.addWidget(result_panel)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([300, 700])
        root.addWidget(splitter, stretch=1)

        self._status_bar = QtWidgets.QStatusBar()
        self._status_bar.setObjectName("ScreenerStatusBar")
        self._status_bar.setSizeGripEnabled(False)
        self._status_label = QtWidgets.QLabel("配置配方后试跑，或等待定时任务写入结果")
        self._status_bar.addWidget(self._status_label, stretch=1)
        root.addWidget(self._status_bar)

    def _release_worker(self, worker: QtCore.QThread | None) -> None:
        release_thread(self._retired_workers, worker)

    def _run_recipe(self, recipe, recipe_id: str) -> None:
        if self._recipe_worker is not None and self._recipe_worker.isRunning():
            return
        self._status_label.setText("正在试跑多因子配方…")
        worker = ScreenerRecipeRunWorker(recipe, recipe_id)
        self._recipe_worker = worker
        worker.finished.connect(self._on_recipe_finished)
        worker.failed.connect(self._on_recipe_failed)
        worker.start()

    def _on_recipe_finished(self, result: ScreenerRunResult, recipe_id: str) -> None:
        worker = self._recipe_worker
        self._recipe_worker = None
        self._release_worker(worker)
        self._apply_result(result)
        save_run(
            condition=result.condition,
            source=result.source,
            rows=self._results,
            total_scanned=result.total_scanned,
            config={"trigger": "manual", "recipe_id": recipe_id},
        )
        self._status_label.setText(
            f"配方试跑完成 · 命中 {len(self._results)} 条 · 扫描 {result.total_scanned} 只"
        )
        self.run_sidebar.refresh()
        sync_screener_page_context(self.main_engine)

    def _on_recipe_failed(self, message: str) -> None:
        worker = self._recipe_worker
        self._recipe_worker = None
        self._release_worker(worker)
        self._status_label.setText(message)

    def _apply_result(self, result: ScreenerRunResult) -> None:
        self._results = list(result.rows)
        self._result_columns = result.columns or resolve_export_columns(self._results)
        populate_screener_results_table(self.result_table, self._results, self._result_columns)
        self._store_screening_results(
            condition=result.condition,
            rows=self._results,
            updated_at=result.updated_at,
        )
        source_label = resolve_result_source_tag(result.source)
        updated = result.updated_at or "-"
        self._summary_label.setText(
            f"「{result.condition}」命中 {len(self._results)} 条 · "
            f"扫描 {result.total_scanned} 只 · {source_label} · 更新 {updated}"
        )

    def on_scheduled_run_complete(self, job_id: str, message: str) -> None:
        self.run_sidebar.refresh()
        self.run_sidebar.set_expanded(True)
        latest = get_run_from_latest_auto(job_id)
        if latest is not None:
            self._load_historical_run(latest.id, from_scheduler=True)
        self._status_label.setText(message)
        if self.event_engine is not None:
            self.event_engine.put(
                Event(EVENT_ORB_ATTENTION, OrbAttentionRequest(source="auto_screener")),
            )

    def _load_historical_run(self, run_id: str, *, from_scheduler: bool = False) -> None:
        record = get_run(run_id)
        if record is None:
            self._status_label.setText("自动选股结果不存在或已删除")
            return
        mark_run_read(run_id)
        self._results = list(record.rows)
        self._result_columns = resolve_export_columns(self._results)
        populate_screener_results_table(self.result_table, self._results, self._result_columns)
        self._store_screening_results(
            condition=record.condition,
            rows=self._results,
            updated_at=record.created_at,
        )
        source_label = resolve_result_source_tag(record.source)
        trigger = str(record.config.get("trigger", ""))
        trigger_note = ""
        if trigger.startswith("scheduled_"):
            reason = record.config.get("reason_summary") or trigger.removeprefix("scheduled_")
            trigger_note = f"自动 · {reason} · "
        elif record.config.get("recipe_id"):
            trigger_note = "配方试跑 · "
        self._summary_label.setText(
            f"[历史] {trigger_note}「{record.condition}」命中 {len(self._results)} 条 · "
            f"扫描 {record.total_scanned} · {source_label} · {record.created_at}"
        )
        if not from_scheduler:
            self._status_label.setText(
                f"[历史] {trigger_note}{len(self._results)} 条 · {record.created_at}"
            )
        self.run_sidebar.refresh()
        sync_screener_page_context(self.main_engine)

    def _on_copy_run_id(self, run_id: str, condition: str) -> None:
        short = run_id[:8] + "…" if len(run_id) > 8 else run_id
        self._status_label.setText(f"已复制 run_id（{condition}）：{short}")

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
        self._status_label.setText(f"已打开 AI，预填解读请求：{condition}")

    def _get_screening_service(self):
        engine = self.main_engine.get_engine(APP_NAME)
        if isinstance(engine, AshareEngine):
            return engine.screening_service
        return None

    def _store_screening_results(self, *, condition: str, rows: list, updated_at: str | None = None) -> None:
        service = self._get_screening_service()
        if service is not None:
            service.set_screening_results(condition=condition, rows=rows, updated_at=updated_at)
            return
        from vnpy_ashare.ai.context_store import set_screening_results

        set_screening_results(condition=condition, rows=rows, updated_at=updated_at)

    def _add_selected_to_watchlist(self) -> None:
        if self._watchlist_service is None:
            QtWidgets.QMessageBox.warning(self, "提示", "自选服务未就绪")
            return
        selected = iter_checked_table_rows(self.result_table)
        if not selected:
            QtWidgets.QMessageBox.information(self, "提示", "请先勾选要加入自选的标的")
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
        self._status_label.setText(msg)

    def _get_backtest_service(self):
        engine = self.main_engine.get_engine(APP_NAME)
        if isinstance(engine, AshareEngine):
            return engine.backtest_service
        return None

    def _download_selected_bars(self) -> None:
        if self._download_worker is not None and self._download_worker.isRunning():
            return
        selected = iter_checked_table_rows(self.result_table)
        if not selected:
            QtWidgets.QMessageBox.information(self, "提示", "请先勾选要下载日 K 的标的")
            return
        self.download_btn.setDisabled(True)
        self._status_label.setText(f"正在下载 {len(selected)} 只日 K…")
        worker = ScreenerBatchDownloadWorker(selected)
        self._download_worker = worker
        worker.finished.connect(self._on_download_finished)
        worker.failed.connect(self._on_download_failed)
        worker.start()

    def _on_download_finished(self, result) -> None:
        worker = self._download_worker
        self._download_worker = None
        self._release_worker(worker)
        self.download_btn.setDisabled(False)
        message = getattr(result, "message", str(result))
        self._status_label.setText(message)

    def _on_download_failed(self, message: str) -> None:
        worker = self._download_worker
        self._download_worker = None
        self._release_worker(worker)
        self.download_btn.setDisabled(False)
        self._status_label.setText(message)

    def _open_backtest_for_selection(self) -> None:
        selected = iter_checked_table_rows(self.result_table)
        if not selected:
            QtWidgets.QMessageBox.information(self, "提示", "请先勾选一只标的进行回测")
            return
        if len(selected) > 1:
            QtWidgets.QMessageBox.information(self, "提示", "「策略回测」仅打开单只；批量请用「批量回测」")
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
        if self._batch_backtest_flow.is_running():
            return
        selected = iter_checked_table_rows(self.result_table)
        if not selected:
            QtWidgets.QMessageBox.information(self, "提示", "请先勾选要批量回测的标的")
            return
        backtest_service = self._get_backtest_service()
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
            QtWidgets.QMessageBox.information(self, "提示", "暂无自动选股结果")
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "导出 CSV", "auto_screener_results.csv", "CSV (*.csv)",
        )
        if not path:
            return
        if not path.lower().endswith(".csv"):
            path += ".csv"
        export_rows_to_csv(self._results, path)
        self._status_label.setText(f"已导出：{path}")

    def activate(self) -> None:
        self.recipe_panel.reload()
        self.run_sidebar.refresh()
        sync_screener_page_context(self.main_engine)

    def deactivate(self) -> None:
        for attr in ("_recipe_worker", "_download_worker"):
            worker = getattr(self, attr, None)
            setattr(self, attr, None)
            release_thread(self._retired_workers, worker)
        self._batch_backtest_flow.release_worker(self._retired_workers)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        self.deactivate()
        super().closeEvent(event)


def get_run_from_latest_auto(job_id: str):
    from vnpy_ashare.screener.run_store import is_auto_run, list_runs

    expected = f"scheduled_{job_id.removeprefix('screen_')}"
    for record in list_runs(limit=10):
        if not is_auto_run(record.config):
            continue
        if str(record.config.get("trigger", "")) == expected:
            return record
    runs = [r for r in list_runs(limit=5) if is_auto_run(r.config)]
    return runs[0] if runs else None
