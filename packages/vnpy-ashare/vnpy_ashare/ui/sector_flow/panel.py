"""板块资金监控主面板。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.domain.sector_flow import SectorFlowRow, SectorFlowSnapshot
from vnpy_ashare.ui.sector_flow.detail_panel import SectorFlowDetailPanel
from vnpy_ashare.ui.sector_flow.table import SectorFlowTable
from vnpy_common.ui.loading_overlay import LoadingContentHost
from vnpy_common.ui.theme import theme_manager
from vnpy_common.ui.theme.build_extra import build_sector_flow_stylesheet

_TAB_INFLOW = 0
_TAB_OUTFLOW = 1
_TAB_DIVERGENCE = 2
_TAB_INDUSTRY = 0
_TAB_CONCEPT = 1
_DETAIL_WIDTH = 260


class SectorFlowPanel(QtWidgets.QWidget):
    refresh_requested = QtCore.Signal()
    ai_requested = QtCore.Signal()
    screener_requested = QtCore.Signal()
    sector_kind_changed = QtCore.Signal(str)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("SectorFlowPanel")

        self._table = SectorFlowTable(self)
        self._active_tab = _TAB_INFLOW
        self._sector_kind = "industry"
        self._inflow_rows: list[SectorFlowRow] = []
        self._outflow_rows: list[SectorFlowRow] = []
        self._divergence_rows: list[SectorFlowRow] = []

        self._summary = QtWidgets.QLabel("")
        self._summary.setObjectName("SectorFlowSummary")

        toolbar = QtWidgets.QHBoxLayout()
        toolbar.setSpacing(8)
        self._refresh_btn = QtWidgets.QPushButton("刷新")
        self._refresh_btn.setObjectName("SecondaryButton")
        self._refresh_btn.clicked.connect(self.refresh_requested.emit)
        self._ai_btn = QtWidgets.QPushButton("AI 解读")
        self._ai_btn.setObjectName("ActionButton")
        self._ai_btn.clicked.connect(self.ai_requested.emit)
        self._screener_btn = QtWidgets.QPushButton("成分选股")
        self._screener_btn.setObjectName("SecondaryButton")
        self._screener_btn.setToolTip("对选中行业成分按涨幅筛选，跳转选股页")
        self._screener_btn.clicked.connect(self.screener_requested.emit)

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

        self._tab_group = QtWidgets.QButtonGroup(self)
        self._tab_group.setExclusive(True)
        self._tab_group.addButton(self._tab_inflow_btn, _TAB_INFLOW)
        self._tab_group.addButton(self._tab_outflow_btn, _TAB_OUTFLOW)
        self._tab_group.addButton(self._tab_divergence_btn, _TAB_DIVERGENCE)
        self._tab_group.idClicked.connect(self._switch_tab)

        toolbar.addWidget(self._summary, stretch=1)
        toolbar.addWidget(self._tab_industry_btn)
        toolbar.addWidget(self._tab_concept_btn)
        toolbar.addWidget(self._tab_inflow_btn)
        toolbar.addWidget(self._tab_outflow_btn)
        toolbar.addWidget(self._tab_divergence_btn)
        toolbar.addWidget(self._refresh_btn)
        toolbar.addWidget(self._screener_btn)
        toolbar.addWidget(self._ai_btn)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        layout.addLayout(toolbar)

        self._detail = SectorFlowDetailPanel(self)
        self._splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        self._splitter.setObjectName("SectorFlowSplitter")
        self._splitter.setChildrenCollapsible(False)
        self._splitter.addWidget(self._table)
        self._splitter.addWidget(self._detail)
        self._splitter.setStretchFactor(0, 1)
        self._splitter.setStretchFactor(1, 0)
        self._splitter.setSizes([720, _DETAIL_WIDTH])
        self._content_host = LoadingContentHost(self._splitter)
        layout.addWidget(self._content_host, stretch=1)


        theme_manager().bind_stylesheet(self, extra=build_sector_flow_stylesheet)

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
        self._screener_btn.setEnabled(normalized == "industry")
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
        self._screener_btn.setEnabled(enabled and self._sector_kind == "industry")
        self._tab_industry_btn.setEnabled(enabled)
        self._tab_concept_btn.setEnabled(enabled)
        self._tab_inflow_btn.setEnabled(enabled)
        self._tab_outflow_btn.setEnabled(enabled)
        self._tab_divergence_btn.setEnabled(enabled)

    def apply_snapshot(self, snapshot: SectorFlowSnapshot) -> None:
        if snapshot.sector_kind == "concept":
            self._sector_kind = "concept"
            self._tab_concept_btn.setChecked(True)
        else:
            self._sector_kind = "industry"
            self._tab_industry_btn.setChecked(True)
        self._screener_btn.setEnabled(self._sector_kind == "industry")
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
            parts.append(f"净流入 {snapshot.top_inflow_name} {snapshot.top_inflow_yi:+.1f}亿")
        if snapshot.top_outflow_name:
            parts.append(f"净流出 {snapshot.top_outflow_name} {snapshot.top_outflow_yi:+.1f}亿")
        self._summary.setText(" · ".join(parts) if parts else "暂无板块数据")
        self._render_active_tab()

    def _switch_sector_kind(self, tab_id: int) -> None:
        kind = "concept" if tab_id == _TAB_CONCEPT else "industry"
        if kind == self._sector_kind:
            return
        self._sector_kind = kind
        self._screener_btn.setEnabled(kind == "industry")
        self.sector_kind_changed.emit(kind)

    def _switch_tab(self, tab_id: int) -> None:
        self._active_tab = tab_id
        self._render_active_tab()

    def _render_active_tab(self) -> None:
        self._table.set_divergence_mode(self._active_tab == _TAB_DIVERGENCE)
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
                self._table.set_empty_hint("暂无净流出行业（当前各行业主力净额均为正或零）")
                return
            self._table.set_rows(rows)
            return
        rows = self._inflow_rows
        if not rows:
            self._table.set_empty_hint("暂无净流入行业（当前各行业主力净额均为负或零）")
            return
        self._table.set_rows(rows)

    def focus_sectors(self, sector_ids: set[str]) -> None:
        if not sector_ids:
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
