"""板块资金概览面板。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.domain.market.sector_flow import SectorFlowOverviewSnapshot
from vnpy_ashare.services.sector_flow import format_sector_net_flow_yi
from vnpy_ashare.ui.sector_flow.overview_chart import SectorFlowOverviewChart, _LINE_COLORS
from vnpy_ashare.ui.sector_flow.overview_legend import SectorFlowOverviewLegend


class SectorFlowOverviewPanel(QtWidgets.QWidget):
    sector_selected = QtCore.Signal(str)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("SectorFlowOverviewPanel")

        self._chip_inflow = QtWidgets.QLabel("")
        self._chip_outflow = QtWidgets.QLabel("")
        self._chip_divergence = QtWidgets.QLabel("")
        self._hint = QtWidgets.QLabel("")
        for chip in (self._chip_inflow, self._chip_outflow, self._chip_divergence):
            chip.setObjectName("SectorFlowOverviewChip")
        self._hint.setObjectName("SectorFlowSummary")
        self._hint.setWordWrap(True)

        chip_row = QtWidgets.QHBoxLayout()
        chip_row.setContentsMargins(0, 0, 0, 0)
        chip_row.setSpacing(8)
        chip_row.addWidget(self._chip_inflow)
        chip_row.addWidget(self._chip_outflow)
        chip_row.addWidget(self._chip_divergence)
        chip_row.addStretch(1)

        self._chart = SectorFlowOverviewChart(self)
        self._legend = SectorFlowOverviewLegend(self)
        self._chart.sector_activated.connect(self._emit_sector)
        self._legend.sector_selected.connect(self._on_legend_selected)

        body = QtWidgets.QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(8)
        body.addWidget(self._chart, stretch=1)
        body.addWidget(self._legend, stretch=0)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addLayout(chip_row)
        layout.addWidget(self._hint)
        layout.addLayout(body, stretch=1)

    def apply_snapshot(self, snapshot: SectorFlowOverviewSnapshot) -> None:
        if snapshot.top_inflow_name:
            self._chip_inflow.setText(f"净流入 {snapshot.top_inflow_name} {format_sector_net_flow_yi(snapshot.top_inflow_yi)}")
        else:
            self._chip_inflow.setText("净流入 —")
        if snapshot.top_outflow_name:
            self._chip_outflow.setText(f"净流出 {snapshot.top_outflow_name} {format_sector_net_flow_yi(snapshot.top_outflow_yi)}")
        else:
            self._chip_outflow.setText("净流出 —")
        self._chip_divergence.setText(f"流入 {snapshot.net_inflow_count} · 流出 {snapshot.net_outflow_count}")
        hint_parts: list[str] = []
        if snapshot.updated_at:
            hint_parts.append(snapshot.updated_at)
        if snapshot.has_intraday_curve:
            hint_parts.append("盘中曲线")
        elif snapshot.empty_hint:
            hint_parts.append(snapshot.empty_hint)
        self._hint.setText(" · ".join(hint_parts))

        self._chart.render_snapshot(snapshot)
        series = list(snapshot.inflow_series) + list(snapshot.outflow_series)
        color_map = {item.sector_id: _LINE_COLORS[index % len(_LINE_COLORS)] for index, item in enumerate(series)}
        self._legend.render_snapshot(snapshot, color_map=color_map)

    def highlight_sector(self, sector_id: str) -> None:
        self._chart.set_highlight(sector_id)
        self._legend.select_sector(sector_id)

    def _on_legend_selected(self, sector_id: str) -> None:
        self.highlight_sector(sector_id)
        self._emit_sector(sector_id)

    def _emit_sector(self, sector_id: str) -> None:
        if sector_id:
            self.sector_selected.emit(sector_id)
