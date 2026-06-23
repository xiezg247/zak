"""条件选股页（Preset / 自定义条件）。"""

from __future__ import annotations

from typing import Any

from vnpy.event import Event, EventEngine
from vnpy.trader.engine import MainEngine
from vnpy.trader.ui import QtCore, QtGui, QtWidgets

from vnpy_ashare.ai.context.screener import build_ask_ai_prompt_for_run
from vnpy_ashare.app.engine_access import (
    get_screening_service,
    get_watchlist_service,
)
from vnpy_ashare.app.events import (
    EVENT_ASK_AI,
    AskAiRequest,
    FillScreenerRequest,
)
from vnpy_ashare.domain.screener.result_row import ScreenerResultRow
from vnpy_ashare.screener.data.screening_status import request_uses_live_quotes
from vnpy_ashare.screener.pattern.pattern_screen import list_pattern_screeners
from vnpy_ashare.screener.preset.presets import SCREENER_CUSTOM
from vnpy_ashare.screener.run.runner import ScreenerRequest, ScreenerRunResult
from vnpy_ashare.services.screening import ScreeningService
from vnpy_ashare.ui.backtest.flow.batch_backtest_flow import BatchBacktestFlow
from vnpy_ashare.ui.features.stock_analysis.host import StockAnalysisHost
from vnpy_ashare.ui.features.stock_analysis.open import wire_stock_analysis_context_menu
from vnpy_ashare.ui.screener.pages.screener_result_presenter import ScreenerResultPresenter
from vnpy_ashare.ui.screener.pages.screener_run_controller import ScreenerRunController
from vnpy_ashare.ui.screener.pages.screener_scheme_controller import ScreenerSchemeController
from vnpy_ashare.ui.screener.pages.screener_selection_controller import ScreenerSelectionController
from vnpy_ashare.ui.screener.pages.screener_session import activate_screener_page, deactivate_screener_page
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
    configure_screener_results_table,
    toggle_select_all_table_rows,
    update_select_all_button,
    wire_screener_results_table,
)
from vnpy_ashare.ui.screener.widgets.screener_run_output_panel import ScreenerRunOutputPanel
from vnpy_ashare.ui.screener.widgets.screener_run_sidebar import ScreenerRunSidebar
from vnpy_ashare.ui.screener.widgets.screener_toolbars import ScreenerResultActionBar, screener_toolbar_separator
from vnpy_common.ui.feedback import PageToastHost, TaskGuard
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
        self._pending_industry: str = ""
        self._download_worker: Any = None
        self._batch_backtest_flow: BatchBacktestFlow | None = None
        self._retired_workers: list[QtCore.QThread] = []
        self._results: list[ScreenerResultRow] = []
        self._result_columns: list[tuple[str, str]] = []
        self._last_run_config: dict[str, Any] = {}
        self._loaded_run_id: str | None = None
        self._watchlist_service = get_watchlist_service(main_engine)

        self._build_ui()
        self._result_presenter = ScreenerResultPresenter(self)
        self._run_controller = ScreenerRunController(self)
        self._selection_controller = ScreenerSelectionController(self)
        self._scheme_controller = ScreenerSchemeController(self)
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
        self.download_btn = self.result_action_bar.download_btn
        self.backtest_btn = self.result_action_bar.backtest_btn
        self.batch_backtest_btn = self.result_action_bar.batch_backtest_btn
        self.reference_peer_btn = self.result_action_bar.reference_peer_btn
        self.filter_ultra_short_btn = self.result_action_bar.filter_ultra_short_btn
        self.select_all_btn.clicked.connect(self._select_all)
        self.add_watchlist_btn.clicked.connect(self._add_selected_to_watchlist)
        self.download_btn.clicked.connect(self._download_selected_bars)
        self.backtest_btn.clicked.connect(self._open_backtest_for_selection)
        self.batch_backtest_btn.clicked.connect(self._run_batch_backtest)
        self.reference_peer_btn.clicked.connect(self._open_reference_peer)
        self.filter_ultra_short_btn.clicked.connect(self._filter_ultra_short_pool)

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
        self._run_controller.run_screening()

    def _cancel_screening(self) -> None:
        self._run_controller.cancel_screening()

    def run_radar_resonance_screen(self) -> None:
        """供雷达共振面板等外部入口跳转并执行选股。"""
        self._run_controller.run_radar_resonance()

    def run_leader_screen(self, *, variant: str = "mainline") -> None:
        """供雷达页 / 主窗口跳转并执行龙头选股。"""
        self._run_controller.run_leader_screen(variant=variant)

    def _run_leader_screen(self, *, variant: str = "mainline") -> None:
        self._run_controller.run_leader_screen(variant=variant)

    def _run_radar_resonance(self) -> None:
        self._run_controller.run_radar_resonance()

    def run_industry_screen(self, industry: str) -> None:
        """供板块资金页等外部入口跳转并执行行业成分选股。"""
        label = str(industry or "").strip()
        if not label:
            self._toast.warning("行业名称为空")
            return
        self.industry_edit.setText(label)
        self._pending_industry = label
        self._run_controller.run_industry_screen()

    def _run_industry_from_form(self) -> None:
        self._run_controller.run_industry_from_form()

    def _run_industry_screen(self) -> None:
        self._run_controller.run_industry_screen()

    def _run_pattern_screen(self) -> None:
        self._run_controller.run_pattern_screen()

    def _open_reference_peer(self) -> None:
        self._selection_controller.open_reference_peer()

    def _apply_screen_result(
        self,
        result: ScreenerRunResult,
        *,
        trigger: str = "manual",
        extra_config: dict[str, Any] | None = None,
    ) -> None:
        self._result_presenter.apply_screen_result(result, trigger=trigger, extra_config=extra_config)

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
        self._result_presenter.load_historical_run(run_id)

    def _filter_ultra_short_pool(self) -> None:
        self._result_presenter.filter_ultra_short_pool()

    def _clear_loaded_run_view(self) -> None:
        self._result_presenter.clear_loaded_run_view()

    def _on_runs_deleted(self, run_ids: list) -> None:
        if self._loaded_run_id is not None and self._loaded_run_id in run_ids:
            self._clear_loaded_run_view()
            self._append_action_log("已删除当前展示的历史运行")

    def _select_all(self) -> None:
        toggle_select_all_table_rows(self.result_table)
        update_select_all_button(self.result_table, self.select_all_btn)

    def _iter_checked_rows(self) -> list[dict[str, Any]]:
        return self._selection_controller.iter_checked_rows()

    def _add_selected_to_watchlist(self) -> None:
        self._selection_controller.add_to_watchlist()

    def _download_selected_bars(self) -> None:
        self._selection_controller.download_selected_bars()

    def _cancel_download(self) -> None:
        self._selection_controller.cancel_download()

    def _on_download_finished(self, result) -> None:
        self._selection_controller.on_download_finished(result)

    def _on_download_failed(self, message: str) -> None:
        self._selection_controller.on_download_failed(message)

    def _open_backtest_for_selection(self) -> None:
        self._selection_controller.open_backtest_for_selection(source_page="条件选股")

    def _run_batch_backtest(self) -> None:
        self._selection_controller.run_batch_backtest(
            source_page="选股",
            default_batch_source="batch_screener",
        )

    def _save_scheme(self) -> None:
        self._scheme_controller.save_scheme()

    def _delete_scheme(self) -> None:
        self._scheme_controller.delete_scheme()

    def _export_csv(self) -> None:
        self._selection_controller.export_csv(
            default_filename="screener_results.csv",
            empty_message="请先运行选股",
        )

    def activate(self) -> None:
        activate_screener_page(self)

    def deactivate(self) -> None:
        deactivate_screener_page(self)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        self.deactivate()
        super().closeEvent(event)
