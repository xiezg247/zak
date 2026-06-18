"""条件选股页（Preset / 自定义条件）。"""

from __future__ import annotations

from typing import Any

from vnpy.event import Event, EventEngine
from vnpy.trader.engine import MainEngine
from vnpy.trader.ui import QtCore, QtGui, QtWidgets

from vnpy_ashare.ai.context.screener import build_ask_ai_prompt_for_run, sync_screener_page_context
from vnpy_ashare.ai.context.symbol import parse_stock_symbol
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
    FillScreenerRequest,
    OrbAttentionRequest,
)
from vnpy_ashare.domain.screener.result_row import ScreenerResultRow
from vnpy_ashare.screener.data.screening_status import build_run_insight_detail, request_uses_live_quotes
from vnpy_ashare.screener.pattern.pattern_screen import list_pattern_screeners
from vnpy_ashare.screener.preset.presets import SCREENER_CUSTOM
from vnpy_ashare.screener.run.run_diff import enrich_condition_run
from vnpy_ashare.screener.run.runner import ScreenerRequest, ScreenerRunResult, build_industry_scheme_config
from vnpy_ashare.screener.sentiment.recession_watchlist_guard import confirm_recession_batch_watchlist
from vnpy_ashare.services.screening import ScreeningService
from vnpy_ashare.services.watchlist_short_term import (
    SHORT_TERM_OBSERVATION_GROUP_NAME,
    add_screener_rows_to_short_term_observation_group,
)
from vnpy_ashare.ui.backtest.flow.batch_backtest_flow import BatchBacktestFlow
from vnpy_ashare.ui.features.stock_analysis.host import StockAnalysisHost
from vnpy_ashare.ui.features.stock_analysis.open import wire_stock_analysis_context_menu
from vnpy_ashare.ui.screener.dialogs.reference_peer_dialog import show_reference_peer_dialog
from vnpy_ashare.ui.screener.widgets.screener_config_section import ScreenerConfigSection
from vnpy_ashare.ui.screener.widgets.screener_hard_filter_panel import ScreenerHardFilterPanel
from vnpy_ashare.ui.screener.widgets.screener_insights import (
    ScreenerResultInsights,
    ScreeningDataStatusBar,
    ScreeningPageStatusController,
)
from vnpy_ashare.ui.screener.widgets.screener_layout import (
    apply_screener_main_splitter,
    configure_screener_config_column,
)
from vnpy_ashare.ui.screener.widgets.screener_results_table import (
    ROW_DATA_ROLE,
    apply_screener_results_view,
    configure_screener_results_table,
    iter_checked_table_rows,
    toggle_select_all_table_rows,
    update_select_all_button,
    wire_screener_results_table,
)
from vnpy_ashare.ui.screener.widgets.screener_run_output_panel import ScreenerRunOutputPanel
from vnpy_ashare.ui.screener.widgets.screener_run_sidebar import ScreenerRunSidebar
from vnpy_ashare.ui.screener.widgets.screener_toolbars import ScreenerResultActionBar, screener_toolbar_separator
from vnpy_ashare.ui.screener.workers.screener_workers import (
    IndustryScreenRunWorker,
    LeaderScreenRunWorker,
    PatternScreenRunWorker,
    RadarResonanceRunWorker,
    ScreenerBatchDownloadWorker,
    ScreenerRunWorker,
)
from vnpy_common.ui.feedback import PageToastHost, TaskGuard, confirm_action
from vnpy_common.ui.qt_helpers import release_thread

_SCHEME_ID_ROLE = QtCore.Qt.ItemDataRole.UserRole + 1


class ScreenerPageWidget(QtWidgets.QWidget):
    """选股页「条件选股」Tab。"""

    def __init__(
        self,
        main_engine: MainEngine,
        event_engine: EventEngine,
        *,
        embedded: bool = False,
    ) -> None:
        super().__init__()
        self.main_engine = main_engine
        self.event_engine = event_engine
        self.setObjectName("MarketRoot")
        self._active = False
        self._embedded = embedded
        self._worker: ScreenerRunWorker | None = None
        self._pattern_worker: PatternScreenRunWorker | None = None
        self._radar_worker: RadarResonanceRunWorker | None = None
        self._leader_worker: LeaderScreenRunWorker | None = None
        self._industry_worker: IndustryScreenRunWorker | None = None
        self._pending_industry: str = ""
        self._download_worker: ScreenerBatchDownloadWorker | None = None
        self._batch_backtest_flow: BatchBacktestFlow | None = None
        self._retired_workers: list[QtCore.QThread] = []
        self._results: list[ScreenerResultRow] = []
        self._result_columns: list[tuple[str, str]] = []
        self._loaded_run_id: str | None = None
        self._watchlist_service = get_watchlist_service(main_engine)

        self._build_ui()
        self._status_controller = ScreeningPageStatusController(
            self,
            self.data_status_bar,
            uses_live_quotes=self._current_uses_live_quotes,
            on_log=self._append_action_log,
            on_toast_error=self._toast.error,
            on_toast_success=self._toast.success,
        )
        self._task_guard = TaskGuard(self._toast)
        self._batch_backtest_flow = BatchBacktestFlow(
            main_engine=main_engine,
            event_engine=event_engine,
            parent=self,
            on_status=self._append_action_log,
        )
        self._reload_preset_combo()
        self._on_preset_changed(0)

    def _screening_service(self) -> ScreeningService | None:
        return get_screening_service(self.main_engine)

    def _build_ui(self) -> None:
        page_layout = QtWidgets.QHBoxLayout(self)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(0)

        self.run_sidebar = ScreenerRunSidebar(mode="strategy", main_engine=self.main_engine, parent=self)
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

        if not self._embedded:
            header = QtWidgets.QHBoxLayout()
            title = QtWidgets.QLabel("条件选股")
            title.setObjectName("PageTitle")
            header.addWidget(title)
            header.addStretch()
            root.addLayout(header)

        self.data_status_bar = ScreeningDataStatusBar(main_panel)
        root.addWidget(self.data_status_bar)

        primary_toolbar = QtWidgets.QHBoxLayout()
        primary_toolbar.setContentsMargins(0, 8, 0, 8)
        primary_toolbar.setSpacing(8)

        self.run_btn = QtWidgets.QPushButton("▶  运行条件选股")
        self.run_btn.setObjectName("PrimaryRunButton")
        self.run_btn.clicked.connect(self._run_screening)
        primary_toolbar.addWidget(self.run_btn)
        primary_toolbar.addWidget(screener_toolbar_separator())

        self.save_scheme_btn = QtWidgets.QPushButton("保存方案")
        self.save_scheme_btn.setObjectName("SecondaryButton")
        self.save_scheme_btn.clicked.connect(self._save_scheme)
        primary_toolbar.addWidget(self.save_scheme_btn)

        self.delete_scheme_btn = QtWidgets.QPushButton("删除方案")
        self.delete_scheme_btn.setObjectName("SecondaryButton")
        self.delete_scheme_btn.clicked.connect(self._delete_scheme)
        primary_toolbar.addWidget(self.delete_scheme_btn)
        primary_toolbar.addWidget(screener_toolbar_separator())

        self.export_btn = QtWidgets.QPushButton("导出 CSV")
        self.export_btn.setObjectName("SecondaryButton")
        self.export_btn.setEnabled(False)
        self.export_btn.clicked.connect(self._export_csv)
        primary_toolbar.addWidget(self.export_btn)

        primary_toolbar.addStretch()
        root.addLayout(primary_toolbar)

        self.result_action_bar = ScreenerResultActionBar(main_panel)
        self.select_all_btn = self.result_action_bar.select_all_btn
        self.add_watchlist_btn = self.result_action_bar.add_watchlist_btn
        self.add_observation_group_btn = self.result_action_bar.add_observation_group_btn
        self.download_btn = self.result_action_bar.download_btn
        self.backtest_btn = self.result_action_bar.backtest_btn
        self.batch_backtest_btn = self.result_action_bar.batch_backtest_btn
        self.reference_peer_btn = self.result_action_bar.reference_peer_btn
        self.select_all_btn.clicked.connect(self._select_all)
        self.add_watchlist_btn.clicked.connect(self._add_selected_to_watchlist)
        self.add_observation_group_btn.clicked.connect(self._add_selected_to_observation_group)
        self.download_btn.clicked.connect(self._download_selected_bars)
        self.backtest_btn.clicked.connect(self._open_backtest_for_selection)
        self.batch_backtest_btn.clicked.connect(self._run_batch_backtest)
        self.reference_peer_btn.clicked.connect(self._open_reference_peer)

        # ── 内容区域（Splitter） ──────────────────────────
        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(1)

        # 左侧：方案配置
        left_column = QtWidgets.QWidget()
        configure_screener_config_column(left_column)
        left_column_layout = QtWidgets.QVBoxLayout(left_column)
        left_column_layout.setContentsMargins(0, 0, 10, 0)
        left_column_layout.setSpacing(0)

        form_panel = QtWidgets.QWidget()
        form_panel.setObjectName("ScreenerFormPanel")
        form_layout = QtWidgets.QVBoxLayout(form_panel)
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.setSpacing(4)

        basic_section = ScreenerConfigSection(
            "基础条件",
            section_id="condition_basic",
            expanded=True,
            parent=form_panel,
        )
        basic_layout = basic_section.content_layout()

        self.preset_combo = QtWidgets.QComboBox()
        self.preset_combo.setObjectName("ToolbarCombo")
        self.preset_combo.currentIndexChanged.connect(self._on_preset_changed)
        basic_layout.addWidget(self.preset_combo)

        self.top_n_spin = QtWidgets.QSpinBox()
        self.top_n_spin.setRange(1, 200)
        self.top_n_spin.setValue(20)
        top_row = QtWidgets.QHBoxLayout()
        top_row.addWidget(QtWidgets.QLabel("Top N"))
        top_row.addWidget(self.top_n_spin)
        top_row.addStretch()
        basic_layout.addLayout(top_row)

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
        basic_layout.addWidget(self.custom_box)

        self.hint_label = QtWidgets.QLabel()
        self.hint_label.setObjectName("ScreenerHint")
        self.hint_label.setWordWrap(True)
        basic_layout.addWidget(self.hint_label)
        form_layout.addWidget(basic_section)

        quick_section = ScreenerConfigSection(
            "快捷选股",
            section_id="condition_quick",
            expanded=False,
            parent=form_panel,
        )
        quick_layout = quick_section.content_layout()

        self.pattern_combo = QtWidgets.QComboBox()
        self.pattern_combo.setObjectName("ToolbarCombo")
        for pattern_name in list_pattern_screeners():
            self.pattern_combo.addItem(pattern_name)
        quick_layout.addWidget(self.pattern_combo)
        self.pattern_run_btn = QtWidgets.QPushButton("运行形态选股")
        self.pattern_run_btn.setObjectName("SecondaryButton")
        self.pattern_run_btn.clicked.connect(self._run_pattern_screen)
        quick_layout.addWidget(self.pattern_run_btn)

        self.radar_resonance_btn = QtWidgets.QPushButton("运行雷达共振")
        self.radar_resonance_btn.setObjectName("SecondaryButton")
        self.radar_resonance_btn.setToolTip("使用雷达页最新共振列表选股（需先在雷达页刷新卡片）")
        self.radar_resonance_btn.clicked.connect(self._run_radar_resonance)
        quick_layout.addWidget(self.radar_resonance_btn)

        self.leader_screen_btn = QtWidgets.QPushButton("运行雷达龙头")
        self.leader_screen_btn.setObjectName("SecondaryButton")
        self.leader_screen_btn.setToolTip("按 leader_score 评分筛选主线龙头（含硬过滤与情绪周期 gate）")
        self.leader_screen_btn.clicked.connect(self._run_leader_screen)
        quick_layout.addWidget(self.leader_screen_btn)

        industry_row = QtWidgets.QHBoxLayout()
        self.industry_edit = QtWidgets.QLineEdit()
        self.industry_edit.setObjectName("ToolbarInput")
        self.industry_edit.setPlaceholderText("输入行业名称，如 银行")
        industry_row.addWidget(self.industry_edit, stretch=1)
        self.industry_run_btn = QtWidgets.QPushButton("运行")
        self.industry_run_btn.setObjectName("SecondaryButton")
        self.industry_run_btn.clicked.connect(self._run_industry_from_form)
        industry_row.addWidget(self.industry_run_btn)
        quick_layout.addLayout(industry_row)
        form_layout.addWidget(quick_section)

        filter_section = ScreenerConfigSection(
            "硬过滤",
            section_id="condition_hard_filter",
            expanded=True,
            parent=form_panel,
        )
        self.hard_filter_panel = ScreenerHardFilterPanel(form_panel)
        self.hard_filter_panel.setTitle("")
        filter_section.set_content(self.hard_filter_panel)
        form_layout.addWidget(filter_section)
        form_layout.addStretch()

        form_scroll = QtWidgets.QScrollArea()
        form_scroll.setObjectName("ScreenerFormScroll")
        form_scroll.setWidgetResizable(True)
        form_scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        form_scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        form_scroll.setWidget(form_panel)
        left_column_layout.addWidget(form_scroll)
        splitter.addWidget(left_column)

        # 右侧：结果表格
        result_panel = QtWidgets.QWidget()
        result_layout = QtWidgets.QVBoxLayout(result_panel)
        result_layout.setContentsMargins(4, 0, 0, 0)
        result_layout.setSpacing(0)

        result_layout.addWidget(self.result_action_bar)

        result_body = QtWidgets.QWidget()
        result_body_layout = QtWidgets.QVBoxLayout(result_body)
        result_body_layout.setContentsMargins(0, 0, 0, 0)
        result_body_layout.setSpacing(0)

        self.result_insights = ScreenerResultInsights(result_body)
        result_body_layout.addWidget(self.result_insights)

        self._empty_result_label = QtWidgets.QLabel("点击「运行条件选股」后在此展示结果")
        self._empty_result_label.setObjectName("ScreenerEmptyResult")
        self._empty_result_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        result_body_layout.addWidget(self._empty_result_label, stretch=1)

        self.result_table = QtWidgets.QTableWidget(0, 0)
        configure_screener_results_table(self.result_table)
        wire_screener_results_table(self.result_table, select_all_btn=self.select_all_btn)
        wire_stock_analysis_context_menu(
            self.result_table,
            host=StockAnalysisHost.from_main_engine(
                self.main_engine,
                event_engine=self.event_engine,
                source_page="条件选股",
                retired_workers=self._retired_workers,
            ),
            row_data_role=ROW_DATA_ROLE,
            parent=self,
        )
        self.result_table.hide()
        result_body_layout.addWidget(self.result_table, stretch=1)
        result_layout.addWidget(result_body, stretch=1)
        splitter.addWidget(result_panel)

        apply_screener_main_splitter(splitter)
        root.addWidget(splitter, stretch=1)

        self.run_output_panel = ScreenerRunOutputPanel(parent=main_panel)
        root.addWidget(self.run_output_panel)

        self._toast = PageToastHost(main_panel)
        root.addWidget(self._toast)

    def _task_lock_widgets(self) -> list[QtWidgets.QWidget]:
        return [
            self.run_btn,
            self.save_scheme_btn,
            self.delete_scheme_btn,
            self.select_all_btn,
            self.add_watchlist_btn,
            self.add_observation_group_btn,
            self.download_btn,
            self.backtest_btn,
            self.batch_backtest_btn,
            self.export_btn,
            self.preset_combo,
            self.top_n_spin,
            self.min_change_spin,
            self.max_change_spin,
            self.min_turnover_spin,
            self.pattern_combo,
            self.pattern_run_btn,
            self.radar_resonance_btn,
            self.leader_screen_btn,
            self.industry_edit,
            self.industry_run_btn,
        ]

    def _current_uses_live_quotes(self) -> bool:
        label = self.preset_combo.currentText()
        scheme_id = self._current_scheme_id()
        return request_uses_live_quotes(preset=label, scheme_id=scheme_id)

    def _append_action_log(self, message: str) -> None:
        if message:
            self.run_output_panel.append_log(message)

    def _optional_spin(self, _label: str, *, maximum: float = 20) -> QtWidgets.QDoubleSpinBox:
        spin = QtWidgets.QDoubleSpinBox()
        spin.setRange(-1, maximum)
        spin.setDecimals(2)
        spin.setSuffix(" %")
        spin.setSpecialValueText("不限")
        spin.setValue(-1)
        return spin

    def _reload_preset_combo(self) -> None:
        service = self._screening_service()
        preset_names = service.list_screeners() if service else []
        schemes = service.list_schemes() if service else []
        current = self.preset_combo.currentText()
        self.preset_combo.blockSignals(True)
        self.preset_combo.clear()
        for name in preset_names:
            self.preset_combo.addItem(name)
            if name.startswith("我的 · "):
                scheme_name = name.removeprefix("我的 · ")
                for scheme in schemes:
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
        service = self._screening_service()
        label = self.preset_combo.currentText()
        preset_key = label.removeprefix("我的 · ") if label.startswith("我的 · ") else label
        preset = service.get_preset(preset_key) if service else None
        if label.startswith("我的 · "):
            scheme_id = self._current_scheme_id()
            if scheme_id and service:
                for scheme in service.list_schemes():
                    if scheme.id == scheme_id:
                        if str(scheme.config.get("kind") or "") == "industry":
                            self.industry_edit.setText(str(scheme.config.get("industry") or ""))
                            self.top_n_spin.setValue(int(scheme.config.get("top_n", 20)))
                            self.custom_box.setVisible(False)
                            industry = str(scheme.config.get("industry") or "")
                            self.hint_label.setText(f"行业成分方案：{industry or '—'} · 运行后将筛选该行业成分并按涨幅排序。")
                            return
                        self.top_n_spin.setValue(int(scheme.config.get("top_n", 20)))
                        self.min_change_spin.setValue(scheme.config.get("min_change_pct") if scheme.config.get("min_change_pct") is not None else -1)
                        self.max_change_spin.setValue(scheme.config.get("max_change_pct") if scheme.config.get("max_change_pct") is not None else -1)
                        self.min_turnover_spin.setValue(scheme.config.get("min_turnover") if scheme.config.get("min_turnover") is not None else -1)
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
            self.hint_label.setText(f"{preset.description}\n需要 .env 中配置 TUSHARE_TOKEN。")
        else:
            self.hint_label.setText(f"{preset.description}\n若 Redis 无快照，请运行「工具 → 立即执行 → 行情采集」。")
        if hasattr(self, "_status_controller"):
            self._status_controller.refresh_status()

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
        self.min_change_spin.setValue(req.min_change_pct if req.min_change_pct is not None else -1)
        self.max_change_spin.setValue(req.max_change_pct if req.max_change_pct is not None else -1)
        self.min_turnover_spin.setValue(req.min_turnover if req.min_turnover is not None else -1)
        self._on_preset_changed(self.preset_combo.currentIndex())
        source = data.source_page or "AI"
        self._append_action_log(f"已从 {source} 预填条件选股，请核对后点击「运行条件选股」")

    def _release_worker(
        self,
        worker: QtCore.QThread | None,
        *,
        timeout_ms: int = 3000,
    ) -> None:
        release_thread(self._retired_workers, worker, timeout_ms=timeout_ms)

    def _run_screening(self) -> None:
        if self._task_guard.active:
            return
        if self._worker is not None and self._worker.isRunning():
            return

        request, _ = self._build_request()
        if request is None:
            return

        self._task_guard.begin(
            "正在运行条件选股…",
            widgets=self._task_lock_widgets(),
            primary=self.run_btn,
            primary_text="▶  运行条件选股",
            primary_handler=self._run_screening,
            on_cancel=self._cancel_screening,
        )
        self.run_output_panel.begin_run(
            label=self.preset_combo.currentText(),
            top_n=self.top_n_spin.value(),
        )

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

    def _cancel_screening(self) -> None:
        if self._worker is not None:
            self._worker.request_cancel()
        if self._pattern_worker is not None:
            self._pattern_worker.request_cancel()
        if self._radar_worker is not None:
            self._radar_worker.request_cancel()
        if self._leader_worker is not None:
            self._leader_worker.request_cancel()
        if self._industry_worker is not None:
            self._industry_worker.request_cancel()

    def run_radar_resonance_screen(self) -> None:
        """供雷达共振面板等外部入口跳转并执行选股。"""
        self._run_radar_resonance()

    def run_leader_screen(self, *, variant: str = "mainline") -> None:
        """供雷达页 / 主窗口跳转并执行龙头选股。"""
        self._run_leader_screen(variant=variant)

    def _run_leader_screen(self, *, variant: str = "mainline") -> None:
        if self._task_guard.active:
            return
        if self._leader_worker is not None and self._leader_worker.isRunning():
            return
        top_n = self.top_n_spin.value()
        self._pending_leader_variant = variant
        self._task_guard.begin(
            "正在运行雷达龙头选股…",
            widgets=self._task_lock_widgets(),
            primary=self.leader_screen_btn,
            primary_text="运行雷达龙头",
            primary_handler=lambda: self._run_leader_screen(variant=variant),
            on_cancel=self._cancel_screening,
        )
        self.run_output_panel.begin_run(label="雷达龙头", top_n=top_n, kind="雷达")
        worker = LeaderScreenRunWorker(
            self.main_engine,
            top_n=top_n,
            variant=variant,
            parent=self,
        )
        self._leader_worker = worker
        worker.finished.connect(self._on_leader_finished)
        worker.failed.connect(self._on_leader_failed)
        worker.start()

    def _on_leader_finished(self, result: ScreenerRunResult) -> None:
        worker = self._leader_worker
        self._leader_worker = None
        self._release_worker(worker)
        if not self._active:
            self._task_guard.end()
            return
        cancelled = self._task_guard.cancelled
        self._task_guard.end()
        if cancelled:
            self.run_output_panel.fail_run("已取消")
            self._toast.info("雷达龙头选股已取消")
            return
        config = {
            "trigger": "radar_leader",
            "leader_variant": getattr(self, "_pending_leader_variant", "mainline"),
        }
        self._apply_screen_result(result, trigger="radar_leader", extra_config=config)

    def _on_leader_failed(self, message: str) -> None:
        worker = self._leader_worker
        self._leader_worker = None
        self._release_worker(worker)
        if not self._active:
            self._task_guard.end()
            return
        cancelled = self._task_guard.cancelled
        self._task_guard.end()
        if cancelled or message == "已取消":
            self.run_output_panel.fail_run("已取消")
            self._toast.info("雷达龙头选股已取消")
            return
        self.run_output_panel.fail_run(message)
        self._toast.error(message)

    def _run_radar_resonance(self) -> None:
        if self._task_guard.active:
            return
        if self._radar_worker is not None and self._radar_worker.isRunning():
            return
        top_n = self.top_n_spin.value()
        self._task_guard.begin(
            "正在运行雷达共振选股…",
            widgets=self._task_lock_widgets(),
            primary=self.radar_resonance_btn,
            primary_text="运行雷达共振",
            primary_handler=self._run_radar_resonance,
            on_cancel=self._cancel_screening,
        )
        self.run_output_panel.begin_run(label="雷达共振", top_n=top_n, kind="雷达")
        worker = RadarResonanceRunWorker(
            self.main_engine,
            top_n=top_n,
            parent=self,
        )
        self._radar_worker = worker
        worker.finished.connect(self._on_radar_finished)
        worker.failed.connect(self._on_radar_failed)
        worker.start()

    def _on_radar_finished(self, result: ScreenerRunResult) -> None:
        worker = self._radar_worker
        self._radar_worker = None
        self._release_worker(worker)
        if not self._active:
            self._task_guard.end()
            return
        cancelled = self._task_guard.cancelled
        self._task_guard.end()
        if cancelled:
            self.run_output_panel.fail_run("已取消")
            self._toast.info("雷达共振选股已取消")
            return
        self._apply_screen_result(result, trigger="radar")

    def _on_radar_failed(self, message: str) -> None:
        worker = self._radar_worker
        self._radar_worker = None
        self._release_worker(worker)
        if not self._active:
            self._task_guard.end()
            return
        cancelled = self._task_guard.cancelled
        self._task_guard.end()
        if cancelled or message == "已取消":
            self.run_output_panel.fail_run("已取消")
            self._toast.info("雷达共振选股已取消")
            return
        self.run_output_panel.fail_run(message)
        self._toast.error(message)

    def run_industry_screen(self, industry: str) -> None:
        """供板块资金页等外部入口跳转并执行行业成分选股。"""
        label = str(industry or "").strip()
        if not label:
            self._toast.warning("行业名称为空")
            return
        self.industry_edit.setText(label)
        self._pending_industry = label
        self._run_industry_screen()

    def _run_industry_from_form(self) -> None:
        industry = self.industry_edit.text().strip()
        if not industry:
            self._toast.warning("请输入行业名称")
            return
        self._pending_industry = industry
        self._run_industry_screen()

    def _run_industry_screen(self) -> None:
        industry = self._pending_industry.strip()
        if not industry:
            self._toast.warning("请先选择行业")
            return
        if self._task_guard.active:
            return
        if self._industry_worker is not None and self._industry_worker.isRunning():
            return
        top_n = self.top_n_spin.value()
        self._task_guard.begin(
            f"正在筛选「{industry}」成分股…",
            widgets=self._task_lock_widgets(),
            primary=None,
            on_cancel=self._cancel_screening,
        )
        self.run_output_panel.begin_run(label=f"{industry} 成分", top_n=top_n, kind="行业")
        worker = IndustryScreenRunWorker(
            self.main_engine,
            industry=industry,
            top_n=top_n,
            parent=self,
        )
        self._industry_worker = worker
        worker.finished.connect(self._on_industry_finished)
        worker.failed.connect(self._on_industry_failed)
        worker.start()

    def _on_industry_finished(self, result: ScreenerRunResult) -> None:
        worker = self._industry_worker
        self._industry_worker = None
        self._release_worker(worker)
        if not self._active:
            self._task_guard.end()
            return
        cancelled = self._task_guard.cancelled
        self._task_guard.end()
        if cancelled:
            self.run_output_panel.fail_run("已取消")
            self._toast.info("行业成分选股已取消")
            return
        industry = self._pending_industry.strip()
        self._apply_screen_result(
            result,
            trigger="industry",
            extra_config={"industry": industry} if industry else None,
        )

    def _on_industry_failed(self, message: str) -> None:
        worker = self._industry_worker
        self._industry_worker = None
        self._release_worker(worker)
        if not self._active:
            self._task_guard.end()
            return
        cancelled = self._task_guard.cancelled
        self._task_guard.end()
        if cancelled or message == "已取消":
            self.run_output_panel.fail_run("已取消")
            self._toast.info("行业成分选股已取消")
            return
        self.run_output_panel.fail_run(message)
        self._toast.error(message)

    def _run_pattern_screen(self) -> None:
        if self._task_guard.active:
            return
        if self._pattern_worker is not None and self._pattern_worker.isRunning():
            return
        pattern = self.pattern_combo.currentText().strip()
        if not pattern:
            return
        top_n = self.top_n_spin.value()
        self._task_guard.begin(
            f"正在运行形态选股「{pattern}」…",
            widgets=self._task_lock_widgets(),
            primary=self.pattern_run_btn,
            primary_text="运行形态选股",
            primary_handler=self._run_pattern_screen,
            on_cancel=self._cancel_screening,
        )
        self.run_output_panel.begin_run(label=pattern, top_n=top_n, kind="形态")
        worker = PatternScreenRunWorker(
            self.main_engine,
            pattern=pattern,
            top_n=top_n,
            parent=self,
        )
        self._pattern_worker = worker
        worker.finished.connect(self._on_pattern_finished)
        worker.failed.connect(self._on_pattern_failed)
        worker.start()

    def _open_reference_peer(self) -> None:
        selected = self._iter_checked_rows()
        if len(selected) != 1:
            self._toast.warning("请勾选恰好一只标的作为标杆")
            return
        row = selected[0]
        vt_symbol = str(row.get("vt_symbol") or "").strip()
        if not vt_symbol:
            self._toast.warning("所选行缺少 vt_symbol")
            return
        name = str(row.get("name") or "")

        def watchlist_add(symbol: str, exchange, stock_name: str = "") -> bool:
            if self._watchlist_service is None:
                return False
            return self._watchlist_service.add(symbol, exchange, stock_name)

        show_reference_peer_dialog(
            vt_symbol=vt_symbol,
            reference_name=name,
            watchlist_add=watchlist_add if self._watchlist_service is not None else None,
            retired_workers=self._retired_workers,
            parent=self,
        )

    def _on_pattern_finished(self, result: ScreenerRunResult) -> None:
        worker = self._pattern_worker
        self._pattern_worker = None
        self._release_worker(worker)
        if not self._active:
            self._task_guard.end()
            return
        cancelled = self._task_guard.cancelled
        self._task_guard.end()
        if cancelled:
            self.run_output_panel.fail_run("已取消")
            self._toast.info("形态选股已取消")
            return
        self._apply_screen_result(
            result,
            trigger="pattern",
            extra_config={"pattern": self.pattern_combo.currentText().strip()},
        )

    def _on_pattern_failed(self, message: str) -> None:
        worker = self._pattern_worker
        self._pattern_worker = None
        self._release_worker(worker)
        if not self._active:
            self._task_guard.end()
            return
        cancelled = self._task_guard.cancelled
        self._task_guard.end()
        if cancelled or message == "已取消":
            self.run_output_panel.fail_run("已取消")
            self._toast.info("形态选股已取消")
            return
        self.run_output_panel.fail_run(message)
        self._toast.error(message)

    def _apply_screen_result(
        self,
        result: ScreenerRunResult,
        *,
        trigger: str = "manual",
        extra_config: dict[str, Any] | None = None,
    ) -> None:
        config: dict[str, Any] = dict(extra_config or {})
        config["trigger"] = trigger
        self._results = list(result.rows)
        if trigger in ("radar", "radar_leader", "industry", "pattern"):
            self._results = enrich_condition_run(
                self._results,
                result.condition,
                config,
                source=result.source,
            )
        service = self._screening_service()
        self._result_columns = result.columns or (service.resolve_export_columns(self._results) if service else [])
        apply_screener_results_view(
            self.result_table,
            self._results,
            self._result_columns,
            empty_label=self._empty_result_label,
            select_all_btn=self.select_all_btn,
            result_action_bar=self.result_action_bar,
            export_btn=self.export_btn,
        )
        if service is not None:
            if trigger == "manual":
                request, _ = self._build_request()
                service.save_manual_run(result, request)
            else:
                service.persist_run_result(result, extra_config=config)
        else:
            self._store_screening_results(
                condition=result.condition,
                rows=self._results,
                updated_at=result.updated_at,
            )
        updated = result.updated_at or "-"
        source_label = service.format_source_tag(result.source) if service else result.source
        summary = f"「{result.condition}」命中 {len(self._results)} 条 · 扫描 {result.total_scanned} 只 · {source_label} · 更新 {updated}"
        insight_detail = build_run_insight_detail(self._results, config if trigger != "manual" else None)
        detail_lines = [f"数据源 {result.source} · 已写入历史运行"]
        if insight_detail:
            detail_lines.append(insight_detail)
        self.result_insights.apply(self._results, config if trigger != "manual" else None)
        self.run_output_panel.complete_run(
            summary=summary,
            detail="\n".join(detail_lines),
        )
        self.run_sidebar.refresh()
        sync_screener_page_context(self.main_engine)
        self._toast.success(f"选股完成，命中 {len(self._results)} 条")
        if self.event_engine is not None:
            self.event_engine.put(
                Event(EVENT_ORB_ATTENTION, OrbAttentionRequest(source="screener")),
            )

    def _on_screen_finished(self, result: ScreenerRunResult) -> None:
        worker = self._worker
        self._worker = None
        self._release_worker(worker)
        if not self._active:
            self._task_guard.end()
            return
        cancelled = self._task_guard.cancelled
        self._task_guard.end()
        if cancelled:
            self.run_output_panel.fail_run("已取消")
            self._toast.info("条件选股已取消")
            return
        self._apply_screen_result(result, trigger="manual")

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
                AskAiRequest(prompt=prompt, source_page="条件选股"),
            )
        )
        self._append_action_log(f"已打开 AI，预填解读请求：{condition}")

    def show_historical_run(self, run_id: str) -> None:
        """供雷达页等外部入口打开历史运行。"""
        self._load_historical_run(run_id)

    def _load_historical_run(self, run_id: str) -> None:
        service = self._screening_service()
        record = service.get_run_record(run_id) if service else None
        if record is None:
            self._append_action_log("历史运行不存在或已删除")
            self._clear_loaded_run_view()
            return
        self._loaded_run_id = run_id
        self._results = list(record.rows)
        self._result_columns = service.resolve_export_columns(self._results) if service else []
        apply_screener_results_view(
            self.result_table,
            self._results,
            self._result_columns,
            empty_label=self._empty_result_label,
            select_all_btn=self.select_all_btn,
            result_action_bar=self.result_action_bar,
            export_btn=self.export_btn,
        )
        self._store_screening_results(
            condition=record.condition,
            rows=self._results,
            updated_at=record.created_at,
        )
        source_label = service.format_source_tag(record.source) if service else record.source
        summary = f"[历史] 「{record.condition}」命中 {len(self._results)} 条 · 扫描 {record.total_scanned} · {source_label} · {record.created_at}"
        self.result_insights.apply(self._results, record.config)
        self.run_output_panel.load_history(summary=summary)
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
            select_all_btn=self.select_all_btn,
            result_action_bar=self.result_action_bar,
            export_btn=self.export_btn,
        )
        self._store_screening_results(condition="", rows=[])
        self.result_insights.clear()

    def _on_runs_deleted(self, run_ids: list) -> None:
        if self._loaded_run_id is not None and self._loaded_run_id in run_ids:
            self._clear_loaded_run_view()
            self._append_action_log("已删除当前展示的历史运行")

    def _on_screen_failed(self, message: str) -> None:
        worker = self._worker
        self._worker = None
        self._release_worker(worker)
        if not self._active:
            self._task_guard.end()
            return
        cancelled = self._task_guard.cancelled
        self._task_guard.end()
        if cancelled or message == "已取消":
            self.run_output_panel.fail_run("已取消")
            self._toast.info("条件选股已取消")
            return
        self.run_output_panel.fail_run(message)
        if message != "已取消":
            self._toast.error(message)

    def _select_all(self) -> None:
        toggle_select_all_table_rows(self.result_table)
        update_select_all_button(self.result_table, self.select_all_btn)

    def _iter_checked_rows(self) -> list[dict[str, Any]]:
        return iter_checked_table_rows(self.result_table)

    def _add_selected_to_watchlist(self) -> None:
        if self._watchlist_service is None:
            self._toast.warning("自选服务未就绪")
            return
        selected = self._iter_checked_rows()
        if not selected:
            self._toast.warning("请先勾选要加入自选的标的")
            return

        if not confirm_recession_batch_watchlist(self):
            return

        added = skipped = 0
        full_hit = False
        for row in selected:
            item = parse_stock_symbol(str(row.get("vt_symbol", "")))
            if item is None:
                skipped += 1
                continue
            name = str(row.get("name", "") or item.name)
            if self._watchlist_service.add(item.symbol, item.exchange, name):
                added += 1
            else:
                reason = self._watchlist_service.add_failure_reason(item.symbol, item.exchange)
                if reason == "full":
                    full_hit = True
                    break
                skipped += 1
        msg = f"新加入 {added} 只"
        if skipped:
            msg += f" · 跳过 {skipped} 只"
        if full_hit:
            msg += f" · 自选已满（最多 {self._watchlist_service.max_items} 只）"
        self._append_action_log(msg)
        self._toast.success(msg)

    def _add_selected_to_observation_group(self) -> None:
        if self._watchlist_service is None:
            self._toast.warning("自选服务未就绪")
            return
        selected = self._iter_checked_rows()
        if not selected:
            self._toast.warning("请先勾选要加入观察组的标的")
            return
        result = add_screener_rows_to_short_term_observation_group(self._watchlist_service, selected)
        if result.group_added == 0 and result.watchlist_added == 0:
            self._toast.warning(f"标的已在「{SHORT_TERM_OBSERVATION_GROUP_NAME}」或无法加入")
            return
        parts = [f"已写入「{SHORT_TERM_OBSERVATION_GROUP_NAME}」{result.group_added} 只"]
        if result.watchlist_added:
            parts.append(f"新入自选 {result.watchlist_added} 只")
        if result.skipped:
            parts.append(f"跳过 {result.skipped} 只")
        msg = " · ".join(parts)
        self._append_action_log(msg)
        self._toast.success(msg)

    def _store_screening_results(
        self,
        *,
        condition: str,
        rows: list,
        updated_at: str | None = None,
    ) -> None:
        service = self._screening_service()
        if service is not None:
            service.set_screening_results(
                condition=condition,
                rows=rows,
                updated_at=updated_at,
            )

    def _download_selected_bars(self) -> None:
        if self._task_guard.active:
            return
        if self._download_worker is not None and self._download_worker.isRunning():
            return
        selected = self._iter_checked_rows()
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
        if cancelled:
            self._append_action_log("日 K 下载已取消")
            self._toast.info("日 K 下载已取消")
            return
        self._append_action_log(message)
        self._toast.error(message)

    def _open_backtest_for_selection(self) -> None:
        selected = self._iter_checked_rows()
        if not selected:
            self._toast.warning("请先勾选一只标的进行回测")
            return
        if len(selected) > 1:
            self._toast.info("「策略回测」仅打开单只；批量请用「批量回测」")
            return
        row = selected[0]
        vt_symbol = str(row.get("vt_symbol", ""))
        if not vt_symbol:
            self._toast.warning("缺少 vt_symbol")
            return
        name = str(row.get("name", ""))
        self.event_engine.put(
            Event(
                EVENT_OPEN_BACKTEST,
                BacktestRequest(
                    vt_symbol=vt_symbol,
                    source_page="条件选股",
                    name=name,
                ),
            )
        )

    def _run_batch_backtest(self) -> None:
        flow = self._batch_backtest_flow
        if flow is None or flow.is_running():
            return
        selected = self._iter_checked_rows()
        if not selected:
            self._toast.warning("请先勾选要批量回测的标的")
            return

        backtest_service = get_backtest_service(self.main_engine)
        strategies = backtest_service.list_strategies() if backtest_service else []
        class_names = [item["class_name"] for item in strategies if item.get("class_name")]
        flow.start(
            selected,
            source_page="选股",
            batch_source="batch_screener",
            list_strategies=lambda: class_names,
            on_running=lambda running: self.batch_backtest_btn.setDisabled(running),
        )

    def _save_scheme(self) -> None:
        service = self._screening_service()
        if service is None:
            self._toast.warning("选股服务未就绪")
            return

        label = self.preset_combo.currentText()
        scheme_id = self._current_scheme_id()
        industry = self.industry_edit.text().strip()

        if label.startswith("我的 · ") and scheme_id:
            for scheme in service.list_schemes():
                if scheme.id != scheme_id:
                    continue
                if str(scheme.config.get("kind") or "") != "industry":
                    self._toast.info("该方案不是行业成分类型，请新建保存")
                    return
                if not industry:
                    self._toast.warning("请输入行业名称")
                    return
                try:
                    service.save_scheme(
                        scheme.name,
                        build_industry_scheme_config(industry, top_n=self.top_n_spin.value()),
                        scheme_id=scheme_id,
                    )
                    self._reload_preset_combo()
                    self._append_action_log(f"已更新行业方案：{scheme.name}")
                    self._toast.success(f"已更新方案：{scheme.name}")
                except Exception as ex:
                    self._toast.error(str(ex))
                return
            self._toast.info("方案不存在或已删除")
            return

        if industry:
            default_name = f"{industry}成分"
            text, ok = QtWidgets.QInputDialog.getText(self, "保存行业方案", "方案名称", text=default_name)
            if not ok or not text.strip():
                return
            try:
                service.save_scheme(
                    text.strip(),
                    build_industry_scheme_config(industry, top_n=self.top_n_spin.value()),
                )
                self._reload_preset_combo()
                saved_name = f"我的 · {text.strip()}"
                index = self.preset_combo.findText(saved_name)
                if index >= 0:
                    self.preset_combo.setCurrentIndex(index)
                self._append_action_log(f"已保存行业方案：{text.strip()}")
                self._toast.success(f"已保存行业方案：{text.strip()}")
            except Exception as ex:
                self._toast.error(str(ex))
            return

        if label.startswith("我的 · "):
            self._toast.info("请选择内置方案或填写行业名称后再保存")
            return
        text, ok = QtWidgets.QInputDialog.getText(self, "保存方案", "方案名称")
        if not ok or not text.strip():
            return
        request, _ = self._build_request()
        if request is None or not request.preset:
            return
        try:
            service.save_scheme(text.strip(), service.build_scheme_config(request))
            self._reload_preset_combo()
            saved_name = f"我的 · {text.strip()}"
            index = self.preset_combo.findText(saved_name)
            if index >= 0:
                self.preset_combo.setCurrentIndex(index)
            self._append_action_log(f"已保存方案：{text.strip()}")
            self._toast.success(f"已保存方案：{text.strip()}")
        except Exception as ex:
            self._toast.error(str(ex))

    def _delete_scheme(self) -> None:
        scheme_id = self._current_scheme_id()
        if not scheme_id:
            self._toast.info("请先选择「我的 · …」方案")
            return
        if not confirm_action(
            self,
            "确认删除",
            f"删除方案「{self.preset_combo.currentText()}」？",
            confirm_text="删除",
            destructive=True,
        ):
            return
        service = self._screening_service()
        if service is None:
            self._toast.warning("选股服务未就绪")
            return
        service.delete_scheme(scheme_id)
        self._reload_preset_combo()
        self._append_action_log("方案已删除")
        self._toast.success("方案已删除")

    def _export_csv(self) -> None:
        if not self._results:
            self._toast.warning("请先运行选股")
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
        service = self._screening_service()
        if service is not None:
            service.export_csv(self._results, path)
        self._append_action_log(f"已导出：{path}")
        self._toast.success(f"已导出 CSV：{path}")

    def activate(self) -> None:
        self._active = True
        self._reload_preset_combo()
        self.run_sidebar.refresh()
        self._status_controller.activate()
        sync_screener_page_context(self.main_engine)

    def deactivate(self) -> None:
        self._active = False
        self._status_controller.deactivate()
        if self._worker is not None:
            self._worker.request_cancel()
        if self._pattern_worker is not None:
            self._pattern_worker.request_cancel()
        if self._download_worker is not None:
            self._download_worker.request_cancel()
        self._task_guard.end()
        for attr in ("_worker", "_pattern_worker", "_download_worker"):
            worker = getattr(self, attr, None)
            setattr(self, attr, None)
            self._release_worker(worker, timeout_ms=0)
        if self._batch_backtest_flow is not None:
            self._batch_backtest_flow.release_worker(self._retired_workers, timeout_ms=0)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        self.deactivate()
        super().closeEvent(event)
