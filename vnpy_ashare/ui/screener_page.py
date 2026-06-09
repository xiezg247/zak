"""策略选股页（Preset / 自定义条件）。"""

from __future__ import annotations

from typing import Any

from vnpy.event import Event, EventEngine

from vnpy_ashare.events import (
    EVENT_ASK_AI,
    EVENT_OPEN_BACKTEST,
    EVENT_ORB_ATTENTION,
    AskAiRequest,
    OrbAttentionRequest,
    BacktestRequest,
    FillScreenerRequest,
)
from vnpy.trader.engine import MainEngine
from vnpy.trader.ui import QtCore, QtGui, QtWidgets

from vnpy_ashare.ai.screener_context import build_ask_ai_prompt_for_run, sync_screener_page_context
from vnpy_ashare.ai.symbol import parse_stock_symbol
from vnpy_ashare.engine import APP_NAME, AshareEngine
from vnpy_ashare.screener.data_source import resolve_result_source_tag
from vnpy_ashare.screener.export import export_rows_to_csv, resolve_export_columns
from vnpy_ashare.screener.presets import SCREENER_CUSTOM, get_preset
from vnpy_ashare.screener.runner import ScreenerRequest, ScreenerRunResult, build_scheme_config, list_all_preset_names
from vnpy_ashare.screener.run_store import get_run, save_run
from vnpy_ashare.screener.scheme_store import delete_scheme, list_schemes, save_scheme
from vnpy_ashare.ui.batch_backtest_flow import BatchBacktestFlow
from vnpy_ashare.ui.qt_helpers import release_thread
from vnpy_ashare.ui.screener_results_table import (
    iter_checked_table_rows,
    populate_screener_results_table,
    select_all_table_rows,
)
from vnpy_ashare.ui.screener_run_sidebar import ScreenerRunSidebar
from vnpy_ashare.ui.styles import TERMINAL_STYLESHEET
from vnpy_ashare.ui.worker import ScreenerBatchDownloadWorker, ScreenerRunWorker

_SCHEME_ID_ROLE = QtCore.Qt.ItemDataRole.UserRole + 1


class ScreenerPageWidget(QtWidgets.QWidget):
    """左侧导航「策略选股」页。"""

    def __init__(self, main_engine: MainEngine, event_engine: EventEngine) -> None:
        super().__init__()
        self.main_engine = main_engine
        self.event_engine = event_engine
        self.setObjectName("MarketRoot")
        self._active = False
        self._worker: ScreenerRunWorker | None = None
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
        self._reload_preset_combo()
        self._on_preset_changed(0)
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

        self.run_sidebar = ScreenerRunSidebar(mode="strategy", parent=self)
        self.run_sidebar.run_selected.connect(self._load_historical_run)
        self.run_sidebar.copy_run_id_requested.connect(self._on_copy_run_id)
        self.run_sidebar.ask_ai_requested.connect(self._on_ask_ai_for_run)
        page_layout.addWidget(self.run_sidebar)

        main_panel = QtWidgets.QWidget()
        root = QtWidgets.QVBoxLayout(main_panel)
        root.setContentsMargins(16, 12, 16, 0)
        root.setSpacing(0)
        page_layout.addWidget(main_panel, stretch=1)

        # ── 工具栏 ──────────────────────────────────────────
        toolbar = QtWidgets.QHBoxLayout()
        toolbar.setContentsMargins(0, 0, 0, 8)
        toolbar.setSpacing(8)

        # 主操作
        self.run_btn = QtWidgets.QPushButton("▶  运行策略选股")
        self.run_btn.setObjectName("PrimaryRunButton")
        self.run_btn.clicked.connect(self._run_screening)
        toolbar.addWidget(self.run_btn)
        toolbar.addWidget(self._toolbar_separator())

        # 方案管理
        self.save_scheme_btn = QtWidgets.QPushButton("保存方案")
        self.save_scheme_btn.setObjectName("SecondaryButton")
        self.save_scheme_btn.clicked.connect(self._save_scheme)
        toolbar.addWidget(self.save_scheme_btn)

        self.delete_scheme_btn = QtWidgets.QPushButton("删除方案")
        self.delete_scheme_btn.setObjectName("SecondaryButton")
        self.delete_scheme_btn.clicked.connect(self._delete_scheme)
        toolbar.addWidget(self.delete_scheme_btn)
        toolbar.addWidget(self._toolbar_separator())

        # 选取操作
        self.select_all_btn = QtWidgets.QPushButton("全 选")
        self.select_all_btn.setObjectName("SecondaryButton")
        self.select_all_btn.clicked.connect(self._select_all)
        toolbar.addWidget(self.select_all_btn)

        self.add_watchlist_btn = QtWidgets.QPushButton("加入自选")
        self.add_watchlist_btn.setObjectName("SecondaryButton")
        self.add_watchlist_btn.clicked.connect(self._add_selected_to_watchlist)
        toolbar.addWidget(self.add_watchlist_btn)

        self.download_btn = QtWidgets.QPushButton("下载日K")
        self.download_btn.setObjectName("SecondaryButton")
        self.download_btn.clicked.connect(self._download_selected_bars)
        toolbar.addWidget(self.download_btn)
        toolbar.addWidget(self._toolbar_separator())

        # 回测分析
        self.backtest_btn = QtWidgets.QPushButton("策略回测")
        self.backtest_btn.setObjectName("SecondaryButton")
        self.backtest_btn.clicked.connect(self._open_backtest_for_selection)
        toolbar.addWidget(self.backtest_btn)

        self.batch_backtest_btn = QtWidgets.QPushButton("批量回测")
        self.batch_backtest_btn.setObjectName("SecondaryButton")
        self.batch_backtest_btn.clicked.connect(self._run_batch_backtest)
        toolbar.addWidget(self.batch_backtest_btn)
        toolbar.addSpacing(16)

        # 导出
        self.export_btn = QtWidgets.QPushButton("CSV")
        self.export_btn.setObjectName("SecondaryButton")
        self.export_btn.clicked.connect(self._export_csv)
        toolbar.addWidget(self.export_btn)

        toolbar.addStretch()
        root.addLayout(toolbar)

        # ── 内容区域（Splitter） ──────────────────────────
        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(1)

        # 左侧：筛选条件面板
        form_panel = QtWidgets.QWidget()
        form_panel.setObjectName("ScreenerFormPanel")
        form_layout = QtWidgets.QVBoxLayout(form_panel)
        form_layout.setContentsMargins(0, 0, 10, 0)
        form_layout.setSpacing(6)

        # 预设方案
        form_layout.addWidget(self._section_label("方案选择"))
        self.preset_combo = QtWidgets.QComboBox()
        self.preset_combo.setObjectName("ToolbarCombo")
        self.preset_combo.currentIndexChanged.connect(self._on_preset_changed)
        form_layout.addWidget(self.preset_combo)

        self.top_n_spin = QtWidgets.QSpinBox()
        self.top_n_spin.setRange(1, 200)
        self.top_n_spin.setValue(20)
        top_row = QtWidgets.QHBoxLayout()
        top_row.addWidget(QtWidgets.QLabel("Top N"))
        top_row.addWidget(self.top_n_spin)
        top_row.addStretch()
        form_layout.addLayout(top_row)

        form_layout.addSpacing(8)

        # 自定义条件
        self.custom_box = QtWidgets.QGroupBox("自定义行情条件")
        self.custom_box.setObjectName("ScreenerFormBox")
        custom_layout = QtWidgets.QFormLayout(self.custom_box)
        custom_layout.setSpacing(6)
        self.min_change_spin = self._optional_spin("最低涨幅")
        self.max_change_spin = self._optional_spin("最高涨幅")
        self.min_turnover_spin = self._optional_spin("最低换手", maximum=100)
        custom_layout.addRow("最低涨幅", self.min_change_spin)
        custom_layout.addRow("最高涨幅", self.max_change_spin)
        custom_layout.addRow("最低换手", self.min_turnover_spin)
        form_layout.addWidget(self.custom_box)

        # 提示说明
        self.hint_label = QtWidgets.QLabel()
        self.hint_label.setObjectName("ScreenerHint")
        self.hint_label.setWordWrap(True)
        form_layout.addWidget(self.hint_label)
        form_layout.addStretch()
        splitter.addWidget(form_panel)

        # 右侧：结果区域
        result_panel = QtWidgets.QWidget()
        result_layout = QtWidgets.QVBoxLayout(result_panel)
        result_layout.setContentsMargins(4, 0, 0, 0)
        result_layout.setSpacing(4)

        # 结果摘要
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
        self.result_table.setMouseTracking(True)
        result_layout.addWidget(self.result_table, stretch=1)
        splitter.addWidget(result_panel)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([260, 740])
        root.addWidget(splitter, stretch=1)

        # ── 底部状态栏 ─────────────────────────────────────
        self._status_bar = QtWidgets.QStatusBar()
        self._status_bar.setObjectName("ScreenerStatusBar")
        self._status_bar.setSizeGripEnabled(False)
        self._status_label = QtWidgets.QLabel("设定条件后点击「运行策略选股」")
        self._status_bar.addWidget(self._status_label, stretch=1)
        root.addWidget(self._status_bar)

    def _toolbar_separator(self) -> QtWidgets.QFrame:
        sep = QtWidgets.QFrame()
        sep.setObjectName("ToolbarSeparator")
        sep.setFrameShape(QtWidgets.QFrame.Shape.VLine)
        sep.setFixedWidth(1)
        sep.setFixedHeight(22)
        return sep

    def _section_label(self, text: str) -> QtWidgets.QLabel:
        lbl = QtWidgets.QLabel(text)
        lbl.setObjectName("ScreenerSectionLabel")
        return lbl

    def _optional_spin(self, _label: str, *, maximum: float = 20) -> QtWidgets.QDoubleSpinBox:
        spin = QtWidgets.QDoubleSpinBox()
        spin.setRange(-1, maximum)
        spin.setDecimals(2)
        spin.setSuffix(" %")
        spin.setSpecialValueText("不限")
        spin.setValue(-1)
        return spin

    def _reload_preset_combo(self) -> None:
        current = self.preset_combo.currentText()
        self.preset_combo.blockSignals(True)
        self.preset_combo.clear()
        for name in list_all_preset_names(include_saved=True):
            self.preset_combo.addItem(name)
            if name.startswith("我的 · "):
                scheme_name = name.removeprefix("我的 · ")
                for scheme in list_schemes():
                    if scheme.name == scheme_name:
                        self.preset_combo.setItemData(
                            self.preset_combo.count() - 1,
                            scheme.id,
                            _SCHEME_ID_ROLE,
                        )
                        break
        index = self.preset_combo.findText(current)
        if index >= 0:
            self.preset_combo.setCurrentIndex(index)
        self.preset_combo.blockSignals(False)

    def _current_scheme_id(self) -> str | None:
        data = self.preset_combo.currentData(_SCHEME_ID_ROLE)
        return str(data) if data else None

    def _on_preset_changed(self, _index: int) -> None:
        label = self.preset_combo.currentText()
        preset = get_preset(label.removeprefix("我的 · ") if label.startswith("我的 · ") else label)
        if label.startswith("我的 · "):
            scheme_id = self._current_scheme_id()
            if scheme_id:
                for scheme in list_schemes():
                    if scheme.id == scheme_id:
                        self.top_n_spin.setValue(int(scheme.config.get("top_n", 20)))
                        self.min_change_spin.setValue(
                            scheme.config.get("min_change_pct") if scheme.config.get("min_change_pct") is not None else -1
                        )
                        self.max_change_spin.setValue(
                            scheme.config.get("max_change_pct") if scheme.config.get("max_change_pct") is not None else -1
                        )
                        self.min_turnover_spin.setValue(
                            scheme.config.get("min_turnover") if scheme.config.get("min_turnover") is not None else -1
                        )
                        break
            self.custom_box.setVisible(False)
            self.hint_label.setText("已保存方案：运行后将按保存的条件执行。")
            return

        is_custom = label == SCREENER_CUSTOM
        self.custom_box.setVisible(is_custom)
        for spin in (self.min_change_spin, self.max_change_spin, self.min_turnover_spin):
            spin.setEnabled(is_custom)

        if preset is None:
            self.hint_label.setText("")
            return
        if preset.source == "tushare":
            self.hint_label.setText(
                f"{preset.description}\n需要 .env 中配置 TUSHARE_TOKEN。"
            )
        else:
            self.hint_label.setText(
                f"{preset.description}\n"
                "若 Redis 无快照，请运行「工具 → 立即执行 → 行情采集」。"
            )

    def _optional_float(self, spin: QtWidgets.QDoubleSpinBox) -> float | None:
        if not spin.isEnabled() or spin.value() < 0:
            return None
        return spin.value()

    def _build_request(self) -> tuple[ScreenerRequest | None, str | None]:
        label = self.preset_combo.currentText()
        scheme_id = self._current_scheme_id()
        if scheme_id:
            return ScreenerRequest(preset="", top_n=self.top_n_spin.value(), scheme_id=scheme_id), None
        return ScreenerRequest(
            preset=label,
            top_n=self.top_n_spin.value(),
            min_change_pct=self._optional_float(self.min_change_spin),
            max_change_pct=self._optional_float(self.max_change_spin),
            min_turnover=self._optional_float(self.min_turnover_spin),
        ), None

    def apply_request(self, data: FillScreenerRequest) -> None:
        """AI 确认流：预填表单，不自动运行。"""
        self._reload_preset_combo()
        index = self.preset_combo.findText(data.preset_label)
        if index >= 0:
            self.preset_combo.setCurrentIndex(index)

        req = data.request
        self.top_n_spin.setValue(int(req.top_n or 20))
        self.min_change_spin.setValue(
            req.min_change_pct if req.min_change_pct is not None else -1
        )
        self.max_change_spin.setValue(
            req.max_change_pct if req.max_change_pct is not None else -1
        )
        self.min_turnover_spin.setValue(
            req.min_turnover if req.min_turnover is not None else -1
        )
        self._on_preset_changed(self.preset_combo.currentIndex())
        source = data.source_page or "AI"
        self._status_label.setText(f"已从 {source} 预填策略选股条件，请核对后点击「运行策略选股」")

    def _release_worker(self, worker: QtCore.QThread | None) -> None:
        release_thread(self._retired_workers, worker)

    def _run_screening(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            return

        request, _ = self._build_request()
        if request is None:
            return

        self.run_btn.setDisabled(True)
        self._status_label.setText("正在执行选股…")

        worker = ScreenerRunWorker(
            preset=request.preset,
            top_n=request.top_n,
            min_change_pct=request.min_change_pct,
            max_change_pct=request.max_change_pct,
            min_turnover=request.min_turnover,
            scheme_id=request.scheme_id,
        )
        if request.scheme_id:
            worker.preset = self.preset_combo.currentText()
        self._worker = worker
        worker.finished.connect(self._on_screen_finished)
        worker.failed.connect(self._on_screen_failed)
        worker.start()

    def _on_screen_finished(self, result: ScreenerRunResult) -> None:
        worker = self._worker
        self._worker = None
        self._release_worker(worker)
        self.run_btn.setDisabled(False)
        self._results = list(result.rows)
        self._result_columns = result.columns or resolve_export_columns(self._results)
        populate_screener_results_table(self.result_table, self._results, self._result_columns)
        self._store_screening_results(
            condition=result.condition,
            rows=self._results,
            updated_at=result.updated_at,
        )
        request, _ = self._build_request()
        config = build_scheme_config(request) if request else {}
        config["trigger"] = "manual"
        save_run(
            condition=result.condition,
            source=result.source,
            rows=self._results,
            total_scanned=result.total_scanned,
            config=config,
        )
        updated = result.updated_at or "-"
        source_label = resolve_result_source_tag(result.source)
        self._summary_label.setText(
            f"「{result.condition}」命中 {len(self._results)} 条 · "
            f"扫描 {result.total_scanned} 只 · {source_label} · 更新 {updated}"
        )
        self._status_label.setText(
            f"「{result.condition}」命中 {len(self._results)} 条 · "
            f"扫描 {result.total_scanned} 只 · {source_label} · 更新 {updated}"
        )
        self.run_sidebar.refresh()
        sync_screener_page_context(self.main_engine)
        if self.event_engine is not None:
            self.event_engine.put(
                Event(EVENT_ORB_ATTENTION, OrbAttentionRequest(source="screener")),
            )

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
                AskAiRequest(prompt=prompt, source_page="策略选股"),
            )
        )
        self._status_label.setText(f"已打开 AI，预填解读请求：{condition}")

    def _load_historical_run(self, run_id: str) -> None:
        record = get_run(run_id)
        if record is None:
            self._status_label.setText("历史运行不存在或已删除")
            return
        self._results = list(record.rows)
        self._result_columns = resolve_export_columns(self._results)
        populate_screener_results_table(self.result_table, self._results, self._result_columns)
        self._store_screening_results(
            condition=record.condition,
            rows=self._results,
            updated_at=record.created_at,
        )
        source_label = resolve_result_source_tag(record.source)
        self._summary_label.setText(
            f"[历史] 「{record.condition}」命中 {len(self._results)} 条 · "
            f"扫描 {record.total_scanned} · {source_label} · {record.created_at}"
        )
        self._status_label.setText(
            f"[历史] 「{record.condition}」{len(self._results)} 条 · "
            f"扫描 {record.total_scanned} · {source_label} · {record.created_at}"
        )
        sync_screener_page_context(self.main_engine)

    def _on_screen_failed(self, message: str) -> None:
        worker = self._worker
        self._worker = None
        self._release_worker(worker)
        self.run_btn.setDisabled(False)
        self._summary_label.setText("")
        self._status_label.setText(message)

    def _select_all(self) -> None:
        select_all_table_rows(self.result_table)

    def _iter_checked_rows(self) -> list[dict[str, Any]]:
        return iter_checked_table_rows(self.result_table)

    def _add_selected_to_watchlist(self) -> None:
        if self._watchlist_service is None:
            QtWidgets.QMessageBox.warning(self, "提示", "自选服务未就绪")
            return
        selected = self._iter_checked_rows()
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

    def _get_screening_service(self):
        engine = self.main_engine.get_engine(APP_NAME)
        if isinstance(engine, AshareEngine):
            return engine.screening_service
        return None

    def _store_screening_results(
        self,
        *,
        condition: str,
        rows: list,
        updated_at: str | None = None,
    ) -> None:
        service = self._get_screening_service()
        if service is not None:
            service.set_screening_results(
                condition=condition,
                rows=rows,
                updated_at=updated_at,
            )
            return
        from vnpy_ashare.ai.context_store import set_screening_results

        set_screening_results(condition=condition, rows=rows, updated_at=updated_at)

    def _get_backtest_service(self):
        engine = self.main_engine.get_engine(APP_NAME)
        if isinstance(engine, AshareEngine):
            return engine.backtest_service
        return None

    def _download_selected_bars(self) -> None:
        if self._download_worker is not None and self._download_worker.isRunning():
            return
        selected = self._iter_checked_rows()
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
        if not getattr(result, "success", True):
            QtWidgets.QMessageBox.warning(self, "下载日 K", message)

    def _on_download_failed(self, message: str) -> None:
        worker = self._download_worker
        self._download_worker = None
        self._release_worker(worker)
        self.download_btn.setDisabled(False)
        self._status_label.setText(message)
        QtWidgets.QMessageBox.warning(self, "下载日 K", message)

    def _open_backtest_for_selection(self) -> None:
        selected = self._iter_checked_rows()
        if not selected:
            QtWidgets.QMessageBox.information(self, "提示", "请先勾选一只标的进行回测")
            return
        if len(selected) > 1:
            QtWidgets.QMessageBox.information(
                self,
                "提示",
                "「策略回测」仅打开单只；批量请用「批量回测」",
            )
            return
        row = selected[0]
        vt_symbol = str(row.get("vt_symbol", ""))
        if not vt_symbol:
            QtWidgets.QMessageBox.warning(self, "提示", "缺少 vt_symbol")
            return
        name = str(row.get("name", ""))
        self.event_engine.put(
            Event(
                EVENT_OPEN_BACKTEST,
                BacktestRequest(
                    vt_symbol=vt_symbol,
                    source_page="策略选股",
                    name=name,
                ),
            )
        )

    def _run_batch_backtest(self) -> None:
        if self._batch_backtest_flow.is_running():
            return
        selected = self._iter_checked_rows()
        if not selected:
            QtWidgets.QMessageBox.information(self, "提示", "请先勾选要批量回测的标的")
            return

        backtest_service = self._get_backtest_service()
        strategies = backtest_service.list_strategies() if backtest_service else []
        class_names = [item["class_name"] for item in strategies if item.get("class_name")]
        self._batch_backtest_flow.start(
            selected,
            source_page="选股",
            batch_source="batch_screener",
            list_strategies=lambda: class_names,
            on_running=lambda running: self.batch_backtest_btn.setDisabled(running),
        )

    def _save_scheme(self) -> None:
        label = self.preset_combo.currentText()
        if label.startswith("我的 · "):
            QtWidgets.QMessageBox.information(self, "提示", "请选择内置方案或自定义条件后再保存")
            return
        text, ok = QtWidgets.QInputDialog.getText(self, "保存方案", "方案名称")
        if not ok or not text.strip():
            return
        request, _ = self._build_request()
        if request is None or not request.preset:
            return
        try:
            save_scheme(text.strip(), build_scheme_config(request))
            self._reload_preset_combo()
            saved_name = f"我的 · {text.strip()}"
            index = self.preset_combo.findText(saved_name)
            if index >= 0:
                self.preset_combo.setCurrentIndex(index)
            self._status_label.setText(f"已保存方案：{text.strip()}")
        except Exception as ex:
            QtWidgets.QMessageBox.warning(self, "提示", str(ex))

    def _delete_scheme(self) -> None:
        scheme_id = self._current_scheme_id()
        if not scheme_id:
            QtWidgets.QMessageBox.information(self, "提示", "请先选择「我的 · …」方案")
            return
        reply = QtWidgets.QMessageBox.question(
            self,
            "确认删除",
            f"删除方案「{self.preset_combo.currentText()}」？",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
        )
        if reply != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        delete_scheme(scheme_id)
        self._reload_preset_combo()
        self._status_label.setText("方案已删除")

    def _export_csv(self) -> None:
        if not self._results:
            QtWidgets.QMessageBox.information(self, "提示", "请先运行选股")
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "导出 CSV",
            "screener_results.csv",
            "CSV (*.csv)",
        )
        if not path:
            return
        if not path.lower().endswith(".csv"):
            path += ".csv"
        export_rows_to_csv(self._results, path)
        self._status_label.setText(f"已导出：{path}")

    def activate(self) -> None:
        self._active = True
        self._reload_preset_combo()
        self.run_sidebar.refresh()
        sync_screener_page_context(self.main_engine)

    def deactivate(self) -> None:
        self._active = False
        for attr in ("_worker", "_download_worker"):
            worker = getattr(self, attr, None)
            setattr(self, attr, None)
            release_thread(self._retired_workers, worker)
        self._batch_backtest_flow.release_worker(self._retired_workers)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        self.deactivate()
        super().closeEvent(event)
