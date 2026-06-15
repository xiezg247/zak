"""板块资金监控主面板。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.domain.sector_flow import SectorFlowRow, SectorFlowSnapshot
from vnpy_ashare.ui.sector_flow.table import SectorFlowTable
from vnpy_common.ui.theme import theme_manager

_TAB_INFLOW = 0
_TAB_OUTFLOW = 1


class SectorFlowPanel(QtWidgets.QWidget):
    refresh_requested = QtCore.Signal()
    ai_requested = QtCore.Signal()
    screener_requested = QtCore.Signal()

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("SectorFlowPanel")

        self._table = SectorFlowTable(self)
        self._active_tab = _TAB_INFLOW
        self._inflow_rows: list[SectorFlowRow] = []
        self._outflow_rows: list[SectorFlowRow] = []

        self._summary = QtWidgets.QLabel("加载中…")
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

        self._tab_inflow_btn = QtWidgets.QPushButton("净流入")
        self._tab_inflow_btn.setObjectName("OverviewTabButton")
        self._tab_inflow_btn.setCheckable(True)
        self._tab_inflow_btn.setChecked(True)
        self._tab_outflow_btn = QtWidgets.QPushButton("净流出")
        self._tab_outflow_btn.setObjectName("OverviewTabButton")
        self._tab_outflow_btn.setCheckable(True)

        self._tab_group = QtWidgets.QButtonGroup(self)
        self._tab_group.setExclusive(True)
        self._tab_group.addButton(self._tab_inflow_btn, _TAB_INFLOW)
        self._tab_group.addButton(self._tab_outflow_btn, _TAB_OUTFLOW)
        self._tab_group.idClicked.connect(self._switch_tab)

        toolbar.addWidget(self._summary, stretch=1)
        toolbar.addWidget(self._tab_inflow_btn)
        toolbar.addWidget(self._tab_outflow_btn)
        toolbar.addWidget(self._refresh_btn)
        toolbar.addWidget(self._screener_btn)
        toolbar.addWidget(self._ai_btn)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        layout.addLayout(toolbar)
        layout.addWidget(self._table, stretch=1)

        from vnpy_common.ui.theme.build_extra import build_sector_flow_stylesheet

        theme_manager().bind_stylesheet(self, extra=build_sector_flow_stylesheet)

    @property
    def table(self) -> SectorFlowTable:
        return self._table

    def set_loading(self, loading: bool) -> None:
        self._refresh_btn.setEnabled(not loading)

    def apply_snapshot(self, snapshot: SectorFlowSnapshot) -> None:
        if not snapshot.rows:
            hint = snapshot.empty_hint or "暂无板块数据"
            if snapshot.updated_at:
                self._summary.setText(f"{hint} · 更新 {snapshot.updated_at}")
            else:
                self._summary.setText(hint)
            self._inflow_rows = []
            self._outflow_rows = []
            self._table.setRowCount(0)
            return

        self._inflow_rows = list(snapshot.inflow_rows)
        self._outflow_rows = list(snapshot.outflow_rows)

        parts: list[str] = []
        if snapshot.updated_at:
            parts.append(f"更新 {snapshot.updated_at}")
        if snapshot.top_inflow_name:
            parts.append(f"净流入 {snapshot.top_inflow_name} {snapshot.top_inflow_yi:+.1f}亿")
        if snapshot.top_outflow_name:
            parts.append(f"净流出 {snapshot.top_outflow_name} {snapshot.top_outflow_yi:+.1f}亿")
        self._summary.setText(" · ".join(parts) if parts else "暂无板块数据")
        self._render_active_tab()

    def _switch_tab(self, tab_id: int) -> None:
        self._active_tab = tab_id
        self._render_active_tab()

    def _render_active_tab(self) -> None:
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
