"""多因子配方页：配方试跑 + 定时/AI 结果收件箱。"""

from __future__ import annotations

from typing import Any

from vnpy.event import Event, EventEngine
from vnpy.trader.engine import MainEngine
from vnpy.trader.ui import QtCore, QtGui, QtWidgets

from vnpy_ashare.ai.context.screener import build_ask_ai_prompt_for_run, sync_screener_page_context
from vnpy_ashare.app.engine_access import (
    get_screening_service,
    get_watchlist_service,
)
from vnpy_ashare.app.events import (
    EVENT_ASK_AI,
    EVENT_ORB_ATTENTION,
    AskAiRequest,
    FillRecipeRequest,
    OrbAttentionRequest,
)
from vnpy_ashare.domain.screener.result_row import ScreenerResultRow
from vnpy_ashare.screener.data.screening_status import recipe_uses_live_quotes
from vnpy_ashare.screener.recipe.recipe import TriggerKind
from vnpy_ashare.screener.run.runner import ScreenerRunResult
from vnpy_ashare.services.screening import ScreeningService
from vnpy_ashare.ui.backtest.flow.batch_backtest_flow import BatchBacktestFlow
from vnpy_ashare.ui.features.stock_analysis.host import StockAnalysisHost
from vnpy_ashare.ui.features.stock_analysis.open import wire_stock_analysis_context_menu
from vnpy_ashare.ui.screener.pages.auto_screener_result_presenter import AutoScreenerResultPresenter
from vnpy_ashare.ui.screener.pages.auto_screener_run_controller import AutoScreenerRunController
from vnpy_ashare.ui.screener.pages.screener_selection_controller import ScreenerSelectionController
from vnpy_ashare.ui.screener.widgets.screener_config_section import ScreenerConfigSection
from vnpy_ashare.ui.screener.widgets.screener_hard_filter_panel import ScreenerHardFilterPanel
from vnpy_ashare.ui.screener.widgets.screener_insights import (
    ScreenerResultInsights,
    ScreeningDataStatusBar,
    ScreeningPageStatusController,
)
from vnpy_ashare.ui.screener.widgets.screener_layout import (
    SCREENER_CONFIG_DEFAULT_WIDTH,
    apply_screener_main_splitter,
    configure_screener_config_column,
)
from vnpy_ashare.ui.screener.widgets.screener_recipe_panel import ScreenerRecipePanel
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


class AutoScreenerPageWidget(QtWidgets.QWidget):
    """选股页「多因子配方」Tab。"""

    open_scheduler_requested = QtCore.Signal()

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
        self._download_worker: Any = None
        self._batch_backtest_flow: BatchBacktestFlow | None = None
        self._retired_workers: list[QtCore.QThread] = []
        self._results: list[ScreenerResultRow] = []
        self._result_columns: list[tuple[str, str]] = []
        self._last_run_config: dict[str, Any] = {}
        self._loaded_run_id: str | None = None
        self._watchlist_service = get_watchlist_service(main_engine)
        self._active = False
        self._embedded = embedded

        self._build_ui()
        self._result_presenter = AutoScreenerResultPresenter(self)
        self._selection_controller = ScreenerSelectionController(self)
        self._run_controller = AutoScreenerRunController(self)
        self.recipe_panel.run_requested.connect(self._run_controller.run_recipe)
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
        if not self._embedded:
            title = QtWidgets.QLabel("多因子配方")
            title.setObjectName("PageTitle")
            header.addWidget(title)
        header.addStretch()
        self.scheduler_btn = QtWidgets.QPushButton("定时任务设置")
        self.scheduler_btn.setObjectName("SecondaryButton")
        self.scheduler_btn.clicked.connect(self.open_scheduler_requested.emit)
        header.addWidget(self.scheduler_btn)
        root.addLayout(header)

        self.data_status_bar = ScreeningDataStatusBar(main_panel)
        root.addWidget(self.data_status_bar)

        primary_toolbar = QtWidgets.QHBoxLayout()
        primary_toolbar.setContentsMargins(0, 8, 0, 8)
        primary_toolbar.setSpacing(8)

        self.radar_resonance_btn = QtWidgets.QPushButton("雷达共振")
        self.radar_resonance_btn.setObjectName("SecondaryButton")
        self.radar_resonance_btn.setToolTip("使用雷达页最新共振列表选股")
        self.radar_resonance_btn.clicked.connect(self._run_radar_resonance)
        primary_toolbar.addWidget(self.radar_resonance_btn)

        self.leader_screen_btn = QtWidgets.QPushButton("雷达龙头")
        self.leader_screen_btn.setObjectName("SecondaryButton")
        self.leader_screen_btn.setToolTip("按 leader_score 评分筛选主线龙头")
        self.leader_screen_btn.clicked.connect(self._run_leader_screen)
        primary_toolbar.addWidget(self.leader_screen_btn)
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
        self.select_all_btn.clicked.connect(self._select_all)
        self.add_watchlist_btn.clicked.connect(self._add_selected_to_watchlist)
        self.download_btn.clicked.connect(self._download_selected_bars)
        self.backtest_btn.clicked.connect(self._open_backtest_for_selection)
        self.batch_backtest_btn.clicked.connect(self._run_batch_backtest)
        self.reference_peer_btn.clicked.connect(self._open_reference_peer)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(1)

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

        recipe_section = ScreenerConfigSection(
            "配方编辑",
            section_id="recipe_editor",
            expanded=True,
            parent=form_panel,
        )
        recipe_layout = recipe_section.content_layout()

        hint = QtWidgets.QLabel("在此配置多因子配方；定时任务仅引用配方 ID 与 Cron。盘中/盘后任务完成后，结果会出现在左侧自动结果列表。")
        hint.setObjectName("ScreenerHint")
        hint.setWordWrap(True)
        recipe_layout.addWidget(hint)

        self.recipe_panel = ScreenerRecipePanel(parent=form_panel)
        recipe_layout.addWidget(self.recipe_panel)
        form_layout.addWidget(recipe_section)

        filter_section = ScreenerConfigSection(
            "硬过滤",
            section_id="recipe_hard_filter",
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

        self._empty_result_label = QtWidgets.QLabel("试跑配方或选择左侧自动结果后在此展示")
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
                source_page="多因子配方",
                retired_workers=self._retired_workers,
            ),
            row_data_role=ROW_DATA_ROLE,
            parent=self,
        )
        self.result_table.hide()
        result_body_layout.addWidget(self.result_table, stretch=1)
        result_layout.addWidget(result_body, stretch=1)
        splitter.addWidget(result_panel)

        apply_screener_main_splitter(splitter, config_width=SCREENER_CONFIG_DEFAULT_WIDTH + 20)
        root.addWidget(splitter, stretch=1)

        self.run_output_panel = ScreenerRunOutputPanel(parent=main_panel)
        root.addWidget(self.run_output_panel)

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
            self.reference_peer_btn,
            self.radar_resonance_btn,
            self.leader_screen_btn,
            *self.recipe_panel.task_lock_widgets(),
        ]

    def apply_recipe_request(self, data: FillRecipeRequest) -> None:
        """AI 配方草案：选中配方面板，不自动运行。"""
        trigger: TriggerKind = "intraday" if data.trigger_kind == "intraday" else "post_close"
        self.recipe_panel.select_recipe(data.recipe_id, trigger_kind=trigger)
        if data.top_n:
            self.recipe_panel._top_n_spin.setValue(int(data.top_n))
        self._append_action_log(f"已从 {data.source_page or 'AI'} 预填配方 {data.recipe_id}，请核对后试跑")

    def _current_uses_live_quotes(self) -> bool:
        try:
            recipe = self.recipe_panel.build_runtime_recipe()
        except Exception:
            return False
        return recipe_uses_live_quotes(recipe)

    def _append_action_log(self, message: str) -> None:
        if message:
            self.run_output_panel.append_log(message)

    def _open_reference_peer(self) -> None:
        self._selection_controller.open_reference_peer()

    def _release_worker(
        self,
        worker: QtCore.QThread | None,
        *,
        timeout_ms: int = 3000,
    ) -> None:
        release_thread(self._retired_workers, worker, timeout_ms=timeout_ms)

    def run_radar_resonance_screen(self) -> None:
        """供主窗口等入口执行雷达共振选股。"""
        self._run_controller.run_radar_resonance()

    def run_leader_screen(self, *, variant: str = "mainline") -> None:
        """供主窗口等入口执行雷达龙头选股。"""
        self._run_controller.run_leader_screen(variant=variant)

    def _run_radar_resonance(self) -> None:
        self._run_controller.run_radar_resonance()

    def _run_leader_screen(self, *, variant: str = "mainline") -> None:
        self._run_controller.run_leader_screen(variant=variant)

    def _apply_result(
        self,
        result: ScreenerRunResult,
        *,
        prefix: str = "",
        rows: list[ScreenerResultRow] | None = None,
        config: dict[str, Any] | None = None,
    ) -> str:
        return self._result_presenter.apply_result(
            result,
            prefix=prefix,
            rows=rows,
            config=config,
        )

    def on_scheduled_run_complete(self, job_id: str, message: str) -> None:
        self.run_sidebar.refresh()
        self.run_sidebar.set_expanded(True)
        service = self._screening_service()
        latest = service.find_latest_auto_run_for_job(job_id) if service else None
        if latest is not None:
            self._result_presenter.load_historical_run(latest.id, from_scheduler=True)
        self.run_output_panel.append_log(f"[定时] {message}")
        if self.event_engine is not None:
            self.event_engine.put(
                Event(EVENT_ORB_ATTENTION, OrbAttentionRequest(source="auto_screener")),
            )

    def show_historical_run(self, run_id: str) -> None:
        """供雷达页等外部入口打开自动选股历史运行。"""
        self._result_presenter.load_historical_run(run_id)

    def _load_historical_run(self, run_id: str, *, from_scheduler: bool = False) -> None:
        self._result_presenter.load_historical_run(run_id, from_scheduler=from_scheduler)

    def _clear_loaded_run_view(self) -> None:
        self._result_presenter.clear_loaded_run_view()

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
                AskAiRequest(prompt=prompt, source_page="多因子配方"),
            )
        )
        self._append_action_log(f"已打开 AI，预填解读请求：{condition}")

    def _select_all(self) -> None:
        toggle_select_all_table_rows(self.result_table)
        update_select_all_button(self.result_table, self.select_all_btn)

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
        self._selection_controller.open_backtest_for_selection(source_page="多因子配方")

    def _run_batch_backtest(self) -> None:
        self._selection_controller.run_batch_backtest(
            source_page="多因子配方",
            default_batch_source="batch_auto_screener",
            recipe_id_resolver=lambda: self.recipe_panel.current_recipe_id() or None,
        )

    def _export_csv(self) -> None:
        self._selection_controller.export_csv(
            default_filename="auto_screener_results.csv",
            empty_message="暂无多因子配方结果",
        )

    def activate(self) -> None:
        self._active = True
        self.recipe_panel.reload()
        self.run_sidebar.refresh()
        self._status_controller.activate()
        sync_screener_page_context(self.main_engine)

    def deactivate(self) -> None:
        self._active = False
        self._status_controller.deactivate()
        self._run_controller.cancel_runs()
        if self._download_worker is not None:
            self._download_worker.request_cancel()
        self._task_guard.end()
        self._run_controller.release_workers(timeout_ms=0)
        worker = self._download_worker
        self._download_worker = None
        self._release_worker(worker, timeout_ms=0)
        if self._batch_backtest_flow is not None:
            self._batch_backtest_flow.release_worker(self._retired_workers, timeout_ms=0)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        self.deactivate()
        super().closeEvent(event)
