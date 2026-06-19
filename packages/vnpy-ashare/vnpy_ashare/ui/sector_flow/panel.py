"""板块资金监控主面板。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.domain.market.sector_flow import (
    SectorFlowOutlookBundle,
    SectorFlowRotationSnapshot,
    SectorFlowRow,
    SectorFlowSnapshot,
)
from vnpy_ashare.quotes.radar.outlook_strategy_prefs import (
    load_sector_flow_outlook_strategy_class,
    outlook_strategy_options,
)
from vnpy_ashare.services.sector_flow import format_sector_net_flow_yi
from vnpy_ashare.services.sector_flow_outlook import OUTLOOK_BIAS_LABELS, filter_outlook_rows
from vnpy_ashare.services.sector_flow_outlook_strategy import strategy_outlook_cache_ready
from vnpy_ashare.services.sector_flow_outlook_compare import filter_compare_rows
from vnpy_ashare.services.sector_flow_rotation import FLOW_PATTERN_LABELS, filter_rotation_rows
from vnpy_ashare.ui.sector_flow.detail_panel import SectorFlowDetailPanel
from vnpy_ashare.ui.sector_flow.outlook_table import SectorFlowOutlookTable
from vnpy_ashare.ui.sector_flow.rotation_table import SectorFlowRotationTable
from vnpy_ashare.ui.sector_flow.table import SectorFlowTable
from vnpy_common.ui.loading_overlay import LoadingContentHost
from vnpy_common.ui.theme.build_extra import build_sector_flow_stylesheet
from vnpy_common.ui.theme.manager import theme_manager

_TAB_INFLOW = 0
_TAB_OUTFLOW = 1
_TAB_DIVERGENCE = 2
_TAB_ROTATION = 3
_TAB_OUTLOOK = 4
_TAB_INDUSTRY = 0
_TAB_CONCEPT = 1
_OUTLOOK_MODE_COMPARE = "compare"
_OUTLOOK_MODE_CONTINUATION = "continuation"
_OUTLOOK_MODE_STRATEGY = "strategy"
_COMPARE_FILTER_LABELS = ("全部", "一致", "分歧")
_DETAIL_WIDTH = 280


def _tab_group_layout(*buttons: QtWidgets.QPushButton) -> QtWidgets.QHBoxLayout:
    layout = QtWidgets.QHBoxLayout()
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(4)
    for button in buttons:
        layout.addWidget(button)
    return layout


def _toolbar_separator(parent: QtWidgets.QWidget) -> QtWidgets.QFrame:
    line = QtWidgets.QFrame(parent)
    line.setObjectName("SectorFlowToolbarSep")
    line.setFrameShape(QtWidgets.QFrame.Shape.VLine)
    line.setFrameShadow(QtWidgets.QFrame.Shadow.Plain)
    line.setFixedWidth(1)
    return line


class SectorFlowPanel(QtWidgets.QWidget):
    refresh_requested = QtCore.Signal()
    ai_requested = QtCore.Signal()
    sector_kind_changed = QtCore.Signal(str)
    view_tab_changed = QtCore.Signal(int)
    outlook_strategy_changed = QtCore.Signal(str)
    outlook_strategy_scan_requested = QtCore.Signal()

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("SectorFlowPanel")

        self._table = SectorFlowTable(self)
        self._rotation_table = SectorFlowRotationTable(self)
        self._outlook_table = SectorFlowOutlookTable(self)
        self._table_stack = QtWidgets.QStackedWidget(self)
        self._table_stack.setObjectName("SectorFlowTableStack")
        self._table_stack.addWidget(self._table)
        self._table_stack.addWidget(self._rotation_table)
        self._table_stack.addWidget(self._outlook_table)
        self._active_tab = _TAB_INFLOW
        self._sector_kind = "industry"
        self._inflow_rows: list[SectorFlowRow] = []
        self._outflow_rows: list[SectorFlowRow] = []
        self._divergence_rows: list[SectorFlowRow] = []
        self._rotation_snapshot: SectorFlowRotationSnapshot | None = None
        self._outlook_bundle: SectorFlowOutlookBundle | None = None
        self._rotation_pattern = ""
        self._outlook_mode = _OUTLOOK_MODE_COMPARE
        self._outlook_filter = ""

        self._summary = QtWidgets.QLabel("")
        self._summary.setObjectName("SectorFlowSummary")

        self._refresh_btn = QtWidgets.QPushButton("刷新")
        self._refresh_btn.setObjectName("SecondaryButton")
        self._refresh_btn.clicked.connect(self.refresh_requested.emit)
        self._ai_btn = QtWidgets.QPushButton("AI 解读")
        self._ai_btn.setObjectName("ActionButton")
        self._ai_btn.clicked.connect(self.ai_requested.emit)

        self._tab_industry_btn = QtWidgets.QPushButton("行业")
        self._tab_industry_btn.setObjectName("OverviewTabButton")
        self._tab_industry_btn.setCheckable(True)
        self._tab_industry_btn.setChecked(True)
        self._tab_industry_btn.setToolTip("盘中为行情聚合估算；盘后为东财官方行业日终榜")
        self._tab_concept_btn = QtWidgets.QPushButton("概念")
        self._tab_concept_btn.setObjectName("OverviewTabButton")
        self._tab_concept_btn.setCheckable(True)
        self._tab_concept_btn.setToolTip("同花顺/东财概念板块日终资金流")

        self._kind_group = QtWidgets.QButtonGroup(self)
        self._kind_group.setExclusive(True)
        self._kind_group.addButton(self._tab_industry_btn, _TAB_INDUSTRY)
        self._kind_group.addButton(self._tab_concept_btn, _TAB_CONCEPT)
        self._kind_group.idClicked.connect(self._switch_sector_kind)

        self._tab_inflow_btn = QtWidgets.QPushButton("净流入")
        self._tab_inflow_btn.setObjectName("OverviewTabButton")
        self._tab_inflow_btn.setCheckable(True)
        self._tab_inflow_btn.setChecked(True)
        self._tab_outflow_btn = QtWidgets.QPushButton("净流出")
        self._tab_outflow_btn.setObjectName("OverviewTabButton")
        self._tab_outflow_btn.setCheckable(True)
        self._tab_divergence_btn = QtWidgets.QPushButton("背离")
        self._tab_divergence_btn.setObjectName("OverviewTabButton")
        self._tab_divergence_btn.setCheckable(True)
        self._tab_divergence_btn.setToolTip("价涨但资金流出，或价跌但资金流入")
        self._tab_rotation_btn = QtWidgets.QPushButton("近15日轮动")
        self._tab_rotation_btn.setObjectName("OverviewTabButton")
        self._tab_rotation_btn.setCheckable(True)
        self._tab_rotation_btn.setToolTip("近15个交易日板块主力净流入方向矩阵（日终官方数据）")
        self._tab_outlook_btn = QtWidgets.QPushButton("未来3日展望")
        self._tab_outlook_btn.setObjectName("OverviewTabButton")
        self._tab_outlook_btn.setCheckable(True)
        self._tab_outlook_btn.setToolTip("未来3个交易日行业资金统计延续与策略聚合对照（非预测）")

        self._tab_group = QtWidgets.QButtonGroup(self)
        self._tab_group.setExclusive(True)
        self._tab_group.addButton(self._tab_inflow_btn, _TAB_INFLOW)
        self._tab_group.addButton(self._tab_outflow_btn, _TAB_OUTFLOW)
        self._tab_group.addButton(self._tab_divergence_btn, _TAB_DIVERGENCE)
        self._tab_group.addButton(self._tab_rotation_btn, _TAB_ROTATION)
        self._tab_group.addButton(self._tab_outlook_btn, _TAB_OUTLOOK)
        self._tab_group.idClicked.connect(self._switch_tab)

        self._rotation_filter_host = QtWidgets.QWidget(self)
        self._rotation_filter_host.setObjectName("SectorFlowRotationFilters")
        self._rotation_filter_host.hide()
        self._pattern_all_btn = QtWidgets.QPushButton("全部")
        self._pattern_all_btn.setObjectName("OverviewTabButton")
        self._pattern_all_btn.setCheckable(True)
        self._pattern_all_btn.setChecked(True)
        self._pattern_buttons: list[QtWidgets.QPushButton] = []
        self._pattern_group = QtWidgets.QButtonGroup(self)
        self._pattern_group.setExclusive(True)
        self._pattern_group.addButton(self._pattern_all_btn, 0)
        for index, label in enumerate(FLOW_PATTERN_LABELS, start=1):
            button = QtWidgets.QPushButton(label)
            button.setObjectName("OverviewTabButton")
            button.setCheckable(True)
            self._pattern_buttons.append(button)
            self._pattern_group.addButton(button, index)
        self._pattern_group.idClicked.connect(self._switch_rotation_pattern)
        rotation_filter_row = QtWidgets.QHBoxLayout(self._rotation_filter_host)
        rotation_filter_row.setContentsMargins(0, 0, 0, 0)
        rotation_filter_row.setSpacing(4)
        rotation_filter_row.addWidget(QtWidgets.QLabel("方向筛选"))
        rotation_filter_row.addLayout(_tab_group_layout(self._pattern_all_btn, *self._pattern_buttons))
        rotation_filter_row.addStretch(1)

        self._outlook_filter_host = QtWidgets.QWidget(self)
        self._outlook_filter_host.setObjectName("SectorFlowOutlookFilters")
        self._outlook_filter_host.hide()
        self._outlook_compare_btn = QtWidgets.QPushButton("对照")
        self._outlook_compare_btn.setObjectName("OverviewTabButton")
        self._outlook_compare_btn.setCheckable(True)
        self._outlook_compare_btn.setChecked(True)
        self._outlook_continuation_btn = QtWidgets.QPushButton("延续A")
        self._outlook_continuation_btn.setObjectName("OverviewTabButton")
        self._outlook_continuation_btn.setCheckable(True)
        self._outlook_strategy_btn = QtWidgets.QPushButton("策略B")
        self._outlook_strategy_btn.setObjectName("OverviewTabButton")
        self._outlook_strategy_btn.setCheckable(True)
        self._outlook_mode_group = QtWidgets.QButtonGroup(self)
        self._outlook_mode_group.setExclusive(True)
        self._outlook_mode_group.addButton(self._outlook_compare_btn, 0)
        self._outlook_mode_group.addButton(self._outlook_continuation_btn, 1)
        self._outlook_mode_group.addButton(self._outlook_strategy_btn, 2)
        self._outlook_mode_group.idClicked.connect(self._switch_outlook_mode)

        self._outlook_filter_all_btn = QtWidgets.QPushButton("全部")
        self._outlook_filter_all_btn.setObjectName("OverviewTabButton")
        self._outlook_filter_all_btn.setCheckable(True)
        self._outlook_filter_all_btn.setChecked(True)
        self._outlook_filter_buttons: list[QtWidgets.QPushButton] = []
        self._outlook_filter_group = QtWidgets.QButtonGroup(self)
        self._outlook_filter_group.setExclusive(True)
        self._outlook_filter_group.addButton(self._outlook_filter_all_btn, 0)
        self._outlook_filter_group.idClicked.connect(self._switch_outlook_filter)
        outlook_filter_row = QtWidgets.QHBoxLayout(self._outlook_filter_host)
        outlook_filter_row.setContentsMargins(0, 0, 0, 0)
        outlook_filter_row.setSpacing(4)
        outlook_filter_row.addWidget(QtWidgets.QLabel("口径"))
        outlook_filter_row.addLayout(
            _tab_group_layout(self._outlook_compare_btn, self._outlook_continuation_btn, self._outlook_strategy_btn)
        )
        outlook_filter_row.addSpacing(8)
        outlook_filter_row.addWidget(QtWidgets.QLabel("筛选"))
        outlook_filter_row.addWidget(self._outlook_filter_all_btn)
        self._outlook_dynamic_filter_layout = QtWidgets.QHBoxLayout()
        self._outlook_dynamic_filter_layout.setContentsMargins(0, 0, 0, 0)
        self._outlook_dynamic_filter_layout.setSpacing(4)
        outlook_filter_row.addLayout(self._outlook_dynamic_filter_layout)

        self._outlook_strategy_combo = QtWidgets.QComboBox(self._outlook_filter_host)
        self._outlook_strategy_combo.setObjectName("SectorFlowOutlookStrategyCombo")
        self._outlook_strategy_combo.setToolTip("策略 B 聚合使用的信号策略（与雷达未来卡独立配置，共用展望缓存）")
        for option in outlook_strategy_options():
            self._outlook_strategy_combo.addItem(option.label, option.class_name)
        default_class = load_sector_flow_outlook_strategy_class()
        default_index = self._outlook_strategy_combo.findData(default_class)
        if default_index >= 0:
            self._outlook_strategy_combo.setCurrentIndex(default_index)
        self._outlook_strategy_combo.currentIndexChanged.connect(self._emit_outlook_strategy_changed)
        outlook_filter_row.addSpacing(8)
        strategy_label = QtWidgets.QLabel("策略")
        strategy_label.setObjectName("SectorFlowOutlookStrategyLabel")
        outlook_filter_row.addWidget(strategy_label)
        outlook_filter_row.addWidget(self._outlook_strategy_combo)
        self._scan_strategy_btn = QtWidgets.QPushButton("扫描策略B")
        self._scan_strategy_btn.setObjectName("SecondaryButton")
        self._scan_strategy_btn.setToolTip("为当前所选策略扫描全市场关注/可持并写入本地缓存（约1–2分钟）")
        self._scan_strategy_btn.clicked.connect(self.outlook_strategy_scan_requested.emit)
        outlook_filter_row.addWidget(self._scan_strategy_btn)
        outlook_filter_row.addStretch(1)

        toolbar_host = QtWidgets.QWidget(self)
        toolbar_host.setObjectName("SectorFlowToolbar")
        header_row = QtWidgets.QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(8)
        header_row.addWidget(self._summary, stretch=1)
        header_row.addWidget(self._refresh_btn)
        header_row.addWidget(self._ai_btn)

        filter_row = QtWidgets.QHBoxLayout()
        filter_row.setContentsMargins(0, 0, 0, 0)
        filter_row.setSpacing(8)
        filter_row.addLayout(_tab_group_layout(self._tab_industry_btn, self._tab_concept_btn))
        filter_row.addWidget(_toolbar_separator(toolbar_host))
        filter_row.addLayout(_tab_group_layout(self._tab_inflow_btn, self._tab_outflow_btn, self._tab_divergence_btn, self._tab_rotation_btn, self._tab_outlook_btn))
        filter_row.addStretch(1)

        toolbar = QtWidgets.QVBoxLayout(toolbar_host)
        toolbar.setContentsMargins(0, 0, 0, 0)
        toolbar.setSpacing(6)
        toolbar.addLayout(header_row)
        toolbar.addLayout(filter_row)
        toolbar.addWidget(self._rotation_filter_host)
        toolbar.addWidget(self._outlook_filter_host)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        layout.addWidget(toolbar_host)

        self._detail = SectorFlowDetailPanel(self)
        self._splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        self._splitter.setObjectName("SectorFlowSplitter")
        self._splitter.setChildrenCollapsible(False)
        self._splitter.addWidget(self._table_stack)
        self._splitter.addWidget(self._detail)
        self._splitter.setStretchFactor(0, 1)
        self._splitter.setStretchFactor(1, 0)
        self._splitter.setSizes([720, _DETAIL_WIDTH])
        self._default_splitter_sizes = [720, _DETAIL_WIDTH]
        self._content_host = LoadingContentHost(self._splitter)
        layout.addWidget(self._content_host, stretch=1)

        theme_manager().bind_stylesheet(self, extra=build_sector_flow_stylesheet)
        self._sync_view_tab_widgets()

    @property
    def outlook_table(self) -> SectorFlowOutlookTable:
        return self._outlook_table

    @property
    def rotation_table(self) -> SectorFlowRotationTable:
        return self._rotation_table

    @property
    def active_tab(self) -> int:
        return self._active_tab

    @property
    def detail(self) -> SectorFlowDetailPanel:
        return self._detail

    @property
    def table(self) -> SectorFlowTable:
        return self._table

    @property
    def sector_kind(self) -> str:
        return self._sector_kind

    def select_sector_kind(self, kind: str, *, emit: bool = False) -> None:
        normalized = "concept" if str(kind or "").strip().lower() == "concept" else "industry"
        self._sector_kind = normalized
        if normalized == "concept":
            self._tab_concept_btn.setChecked(True)
        else:
            self._tab_industry_btn.setChecked(True)
        if emit:
            self.sector_kind_changed.emit(normalized)

    def set_loading(self, loading: bool, *, message: str | None = None) -> None:
        if message is None:
            message = "正在加载概念板块资金…" if self._sector_kind == "concept" else "正在加载行业板块资金…"
        self._set_toolbar_enabled(not loading)
        if loading:
            self._summary.setText(message)
            hint = "盘中为行情聚合估算，盘后为官方日终榜"
            self._content_host.show_loading(message, hint=hint)
            return
        self._content_host.hide_loading()

    def _set_toolbar_enabled(self, enabled: bool) -> None:
        self._refresh_btn.setEnabled(enabled)
        self._ai_btn.setEnabled(enabled)
        self._tab_industry_btn.setEnabled(enabled)
        self._tab_concept_btn.setEnabled(enabled)
        self._tab_inflow_btn.setEnabled(enabled)
        self._tab_outflow_btn.setEnabled(enabled)
        self._tab_divergence_btn.setEnabled(enabled)
        self._tab_rotation_btn.setEnabled(enabled)
        self._tab_outlook_btn.setEnabled(enabled)
        for button in self._pattern_buttons:
            button.setEnabled(enabled)
        self._pattern_all_btn.setEnabled(enabled)
        self._outlook_compare_btn.setEnabled(enabled)
        self._outlook_continuation_btn.setEnabled(enabled)
        self._outlook_strategy_btn.setEnabled(enabled)
        self._outlook_filter_all_btn.setEnabled(enabled)
        combo = self._outlook_strategy_combo
        if combo is not None:
            try:
                combo.setEnabled(enabled)
            except RuntimeError:
                pass
        for button in self._outlook_filter_buttons:
            button.setEnabled(enabled)
        scan_btn = getattr(self, "_scan_strategy_btn", None)
        if scan_btn is not None:
            try:
                scan_btn.setEnabled(enabled)
            except RuntimeError:
                pass

    def select_view_tab(self, tab_id: int, *, emit: bool = True) -> None:
        if tab_id == _TAB_INFLOW:
            self._tab_inflow_btn.setChecked(True)
        elif tab_id == _TAB_OUTFLOW:
            self._tab_outflow_btn.setChecked(True)
        elif tab_id == _TAB_DIVERGENCE:
            self._tab_divergence_btn.setChecked(True)
        elif tab_id == _TAB_ROTATION:
            self._tab_rotation_btn.setChecked(True)
        elif tab_id == _TAB_OUTLOOK:
            self._tab_outlook_btn.setChecked(True)
        if emit:
            self._switch_tab(tab_id)
        else:
            self._active_tab = tab_id
            self._sync_view_tab_widgets()

    def outlook_strategy_class(self) -> str:
        combo = self._outlook_strategy_combo
        if combo is None:
            return load_sector_flow_outlook_strategy_class()
        try:
            value = combo.currentData()
        except RuntimeError:
            return load_sector_flow_outlook_strategy_class()
        return str(value or load_sector_flow_outlook_strategy_class())

    def set_outlook_strategy_class(self, class_name: str, *, emit: bool = False) -> None:
        combo = self._outlook_strategy_combo
        if combo is None:
            return
        index = combo.findData(class_name)
        if index < 0:
            return
        combo.blockSignals(not emit)
        combo.setCurrentIndex(index)
        combo.blockSignals(False)
        if emit:
            self._emit_outlook_strategy_changed(index)

    def _emit_outlook_strategy_changed(self, _index: int) -> None:
        class_name = self.outlook_strategy_class()
        if class_name:
            self.outlook_strategy_changed.emit(class_name)

    def _sync_outlook_strategy_combo_visible(self) -> None:
        show_strategy = self._outlook_mode in {_OUTLOOK_MODE_COMPARE, _OUTLOOK_MODE_STRATEGY}
        combo = self._outlook_strategy_combo
        if combo is not None:
            try:
                combo.setVisible(show_strategy)
            except RuntimeError:
                pass
        label = self._outlook_filter_host.findChild(QtWidgets.QLabel, "SectorFlowOutlookStrategyLabel")
        if label is not None:
            label.setVisible(show_strategy)
        scan_btn = getattr(self, "_scan_strategy_btn", None)
        if scan_btn is not None:
            try:
                scan_btn.setVisible(show_strategy)
            except RuntimeError:
                pass
        self._sync_scan_strategy_button_state()

    def _sync_scan_strategy_button_state(self) -> None:
        scan_btn = getattr(self, "_scan_strategy_btn", None)
        if scan_btn is None:
            return
        try:
            ready = strategy_outlook_cache_ready(self.outlook_strategy_class())
            scan_btn.setText("刷新策略B" if ready else "扫描策略B")
        except RuntimeError:
            pass

    def _rebuild_outlook_filter_buttons(self) -> None:
        for button in self._outlook_filter_buttons:
            self._outlook_filter_group.removeButton(button)
            button.deleteLater()
        self._outlook_filter_buttons.clear()

        layout = self._outlook_dynamic_filter_layout
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.deleteLater()

        labels = list(_COMPARE_FILTER_LABELS) if self._outlook_mode == _OUTLOOK_MODE_COMPARE else ["全部", *OUTLOOK_BIAS_LABELS]
        self._outlook_filter_all_btn.setChecked(not self._outlook_filter or self._outlook_filter == "全部")
        for index, label in enumerate(labels[1:], start=1):
            button = QtWidgets.QPushButton(label)
            button.setObjectName("OverviewTabButton")
            button.setCheckable(True)
            if self._outlook_filter == label:
                button.setChecked(True)
                self._outlook_filter_all_btn.setChecked(False)
            self._outlook_filter_buttons.append(button)
            self._outlook_filter_group.addButton(button, index)
            layout.addWidget(button)

    def _sync_view_tab_widgets(self) -> None:
        show_rotation_filters = self._active_tab == _TAB_ROTATION
        show_outlook_filters = self._active_tab == _TAB_OUTLOOK
        self._rotation_filter_host.setVisible(show_rotation_filters)
        self._outlook_filter_host.setVisible(show_outlook_filters)
        if show_outlook_filters:
            self._rebuild_outlook_filter_buttons()
            self._sync_outlook_strategy_combo_visible()
        self._detail.set_history_visible(self._active_tab not in {_TAB_ROTATION, _TAB_OUTLOOK})
        if self._active_tab == _TAB_ROTATION:
            self._table_stack.setCurrentWidget(self._rotation_table)
            self._detail.hide()
            total = max(sum(self._splitter.sizes()), 1)
            self._splitter.setSizes([total, 0])
        elif self._active_tab == _TAB_OUTLOOK:
            self._table_stack.setCurrentWidget(self._outlook_table)
            self._detail.hide()
            total = max(sum(self._splitter.sizes()), 1)
            self._splitter.setSizes([total, 0])
        else:
            self._table_stack.setCurrentWidget(self._table)
            self._detail.show()
            self._splitter.setSizes(self._default_splitter_sizes)

    def apply_rotation_snapshot(self, snapshot: SectorFlowRotationSnapshot) -> None:
        self._rotation_snapshot = snapshot
        self._apply_rotation_filter()
        self._update_rotation_summary(snapshot)

    def _update_rotation_summary(self, snapshot: SectorFlowRotationSnapshot) -> None:
        parts: list[str] = []
        if snapshot.empty_hint:
            parts.append(snapshot.empty_hint)
        if snapshot.updated_at:
            parts.append(snapshot.updated_at.replace(" · 近15日轮动", ""))
        filtered = filter_rotation_rows(snapshot.rows, self._rotation_pattern)
        if filtered:
            inflow_rows = [row for row in filtered if row.flow_pattern == "持续流入"]
            if inflow_rows:
                top = inflow_rows[0]
                parts.append(f"持续流入 {top.sector.name} {top.cumulative_net_yi:+.1f}亿")
            if self._rotation_pattern and self._rotation_pattern != "全部":
                parts.append(f"筛选 {self._rotation_pattern} {len(filtered)} 项")
        elif snapshot.rows and self._rotation_pattern:
            parts.append(f"筛选「{self._rotation_pattern}」无匹配板块")
        self._summary.setText(" · ".join(parts) if parts else "近15日板块轮动")

    def _apply_rotation_filter(self) -> None:
        snapshot = self._rotation_snapshot
        if snapshot is None:
            self._rotation_table.set_empty_hint("暂无近15日轮动数据")
            return
        rows = list(filter_rotation_rows(snapshot.rows, self._rotation_pattern))
        self._rotation_table.set_rotation_data(snapshot.trade_dates, rows, empty_hint=snapshot.empty_hint)

    def apply_outlook_bundle(self, bundle: SectorFlowOutlookBundle) -> None:
        self._outlook_bundle = bundle
        self._apply_outlook_filter()
        self._update_outlook_summary(bundle)

    def _update_outlook_summary(self, bundle: SectorFlowOutlookBundle) -> None:
        parts: list[str] = ["统计情景，非资金预测"]
        cont_rows = len(bundle.continuation.rows)
        strat_rows = len(bundle.strategy.rows)
        strategy_hint = str(bundle.strategy.empty_hint or "").strip()

        if cont_rows:
            parts.append(f"延续A {cont_rows} 个行业")
        if strat_rows:
            parts.append(f"策略B {strat_rows} 个行业")
        elif strategy_hint:
            parts.append(strategy_hint)
        elif self._outlook_mode in {_OUTLOOK_MODE_COMPARE, _OUTLOOK_MODE_STRATEGY}:
            parts.append("策略B 暂无数据")

        if bundle.compare_rows and self._outlook_mode == _OUTLOOK_MODE_COMPARE:
            agreed = sum(1 for row in bundle.compare_rows if row.agreement == "一致")
            diverged = sum(1 for row in bundle.compare_rows if row.agreement == "分歧")
            only_cont = sum(1 for row in bundle.compare_rows if row.agreement == "仅延续")
            if agreed or diverged:
                parts.append(f"对照 一致{agreed} 分歧{diverged}")
            elif only_cont and strategy_hint:
                parts.append(f"对照 仅延续A {only_cont}")

        if bundle.continuation.updated_at:
            stamp = bundle.continuation.updated_at.replace(" · 未来3日延续", "")
            if stamp and stamp not in parts:
                parts.append(stamp)
        self._summary.setText(" · ".join(dict.fromkeys(parts)))
        self._sync_scan_strategy_button_state()

    def _compare_empty_hint(self, bundle: SectorFlowOutlookBundle, rows: list) -> str:
        if rows:
            return ""
        strategy_hint = str(bundle.strategy.empty_hint or "").strip()
        if bundle.continuation.rows and strategy_hint:
            return f"{strategy_hint}；延续A 仍有 {len(bundle.continuation.rows)} 个行业可查看"
        return strategy_hint or bundle.continuation.empty_hint or "暂无未来3日展望对照数据"

    def _apply_outlook_filter(self) -> None:
        bundle = self._outlook_bundle
        if bundle is None:
            self._outlook_table.set_empty_hint("暂无未来3日展望数据")
            return
        if self._outlook_mode == _OUTLOOK_MODE_COMPARE:
            rows = list(filter_compare_rows(bundle.compare_rows, self._outlook_filter))
            empty_hint = self._compare_empty_hint(bundle, rows)
            self._outlook_table.set_compare_data(bundle.continuation.forward_dates, rows, empty_hint=empty_hint)
            return
        if self._outlook_mode == _OUTLOOK_MODE_CONTINUATION:
            rows = list(filter_outlook_rows(bundle.continuation.rows, self._outlook_filter))
            self._outlook_table.set_continuation_data(bundle.continuation, rows=rows)
            return
        rows = list(filter_outlook_rows(bundle.strategy.rows, self._outlook_filter))
        self._outlook_table.set_strategy_data(bundle.strategy, rows=rows)

    def _switch_outlook_mode(self, button_id: int) -> None:
        mode_map = {
            0: _OUTLOOK_MODE_COMPARE,
            1: _OUTLOOK_MODE_CONTINUATION,
            2: _OUTLOOK_MODE_STRATEGY,
        }
        self._outlook_mode = mode_map.get(button_id, _OUTLOOK_MODE_COMPARE)
        self._outlook_filter = ""
        self._outlook_filter_all_btn.setChecked(True)
        self._rebuild_outlook_filter_buttons()
        self._sync_outlook_strategy_combo_visible()
        self._apply_outlook_filter()
        bundle = self._outlook_bundle
        if bundle is not None:
            self._update_outlook_summary(bundle)

    def _switch_outlook_filter(self, button_id: int) -> None:
        if button_id == 0:
            self._outlook_filter = ""
        elif self._outlook_mode == _OUTLOOK_MODE_COMPARE:
            labels = list(_COMPARE_FILTER_LABELS)
            self._outlook_filter = labels[button_id] if 0 < button_id < len(labels) else ""
        else:
            labels = ["全部", *OUTLOOK_BIAS_LABELS]
            self._outlook_filter = labels[button_id] if 0 < button_id < len(labels) else ""
        self._apply_outlook_filter()
        bundle = self._outlook_bundle
        if bundle is not None:
            self._update_outlook_summary(bundle)

    def _switch_rotation_pattern(self, button_id: int) -> None:
        if button_id == 0:
            self._rotation_pattern = ""
        else:
            index = button_id - 1
            if 0 <= index < len(FLOW_PATTERN_LABELS):
                self._rotation_pattern = FLOW_PATTERN_LABELS[index]
            else:
                self._rotation_pattern = ""
        self._apply_rotation_filter()
        snapshot = self._rotation_snapshot
        if snapshot is not None:
            self._update_rotation_summary(snapshot)

    def apply_snapshot(self, snapshot: SectorFlowSnapshot) -> None:
        if snapshot.sector_kind == "concept":
            self._sector_kind = "concept"
            self._tab_concept_btn.setChecked(True)
        else:
            self._sector_kind = "industry"
            self._tab_industry_btn.setChecked(True)
        self._table.set_official_mode(snapshot.data_mode != "intraday")

        if not snapshot.rows:
            hint = snapshot.empty_hint or "暂无板块数据"
            if snapshot.updated_at:
                self._summary.setText(f"{hint} · 更新 {snapshot.updated_at}")
            else:
                self._summary.setText(hint)
            self._inflow_rows = []
            self._outflow_rows = []
            self._divergence_rows = []
            self._table.setRowCount(0)
            self._detail.clear()
            return

        self._inflow_rows = list(snapshot.inflow_rows)
        self._outflow_rows = list(snapshot.outflow_rows)
        self._divergence_rows = list(snapshot.divergence_rows)

        parts: list[str] = []
        mode_labels = {
            "intraday": "盘中估算",
            "official_dc": "日终·东财",
            "official_ths": "日终·同花顺",
        }
        mode_label = mode_labels.get(snapshot.data_mode, "")
        if mode_label:
            parts.append(mode_label)
        if snapshot.updated_at:
            parts.append(snapshot.updated_at.replace(" · 盘中估算", ""))
        if snapshot.top_inflow_name:
            parts.append(f"净流入 {snapshot.top_inflow_name} {format_sector_net_flow_yi(snapshot.top_inflow_yi)}")
        if snapshot.top_outflow_name:
            parts.append(f"净流出 {snapshot.top_outflow_name} {format_sector_net_flow_yi(snapshot.top_outflow_yi)}")
        self._summary.setText(" · ".join(parts) if parts else "暂无板块数据")
        self._render_active_tab()

    def _switch_sector_kind(self, tab_id: int) -> None:
        kind = "concept" if tab_id == _TAB_CONCEPT else "industry"
        if kind == self._sector_kind:
            return
        self._sector_kind = kind
        self.sector_kind_changed.emit(kind)

    def _switch_tab(self, tab_id: int) -> None:
        self._active_tab = tab_id
        self._sync_view_tab_widgets()
        if tab_id not in {_TAB_ROTATION, _TAB_OUTLOOK}:
            self._render_active_tab()
        self.view_tab_changed.emit(tab_id)

    def _sector_label(self) -> str:
        return "概念" if self._sector_kind == "concept" else "行业"

    def _render_active_tab(self) -> None:
        self._table.set_divergence_mode(self._active_tab == _TAB_DIVERGENCE)
        sector_label = self._sector_label()
        if self._active_tab == _TAB_DIVERGENCE:
            rows = self._divergence_rows
            if not rows:
                self._table.set_empty_hint("暂无量价背离板块（涨跌幅与主力方向一致）")
                self._detail.clear()
                return
            self._table.set_rows(rows)
            return
        if self._active_tab == _TAB_OUTFLOW:
            rows = self._outflow_rows
            if not rows:
                self._table.set_empty_hint(f"暂无净流出{sector_label}（当前各板块主力净额均为正或零）")
                return
            self._table.set_rows(rows)
            return
        rows = self._inflow_rows
        if not rows:
            self._table.set_empty_hint(f"暂无净流入{sector_label}（当前各板块主力净额均为负或零）")
            return
        self._table.set_rows(rows)

    def focus_sectors(self, sector_ids: set[str]) -> None:
        if not sector_ids:
            return
        if self._active_tab == _TAB_OUTLOOK:
            self._outlook_table.focus_sectors(sector_ids)
            row = self._outlook_table.selected_sector_row()
            if row is not None:
                self._outlook_table.sector_selected.emit(row)
            return
        if self._active_tab == _TAB_ROTATION:
            self._rotation_table.focus_sectors(sector_ids)
            row = self._rotation_table.selected_sector_row()
            if row is not None:
                self._rotation_table.sector_selected.emit(row)
            return
        inflow_hits = {row.sector_id for row in self._inflow_rows} & sector_ids
        outflow_hits = {row.sector_id for row in self._outflow_rows} & sector_ids
        if inflow_hits:
            self._active_tab = _TAB_INFLOW
            self._tab_inflow_btn.setChecked(True)
        elif outflow_hits:
            self._active_tab = _TAB_OUTFLOW
            self._tab_outflow_btn.setChecked(True)
        self._render_active_tab()
        self._table.focus_sectors(sector_ids)
        row = self._table.selected_sector_row()
        if row is not None:
            self._table.sector_selected.emit(row)
