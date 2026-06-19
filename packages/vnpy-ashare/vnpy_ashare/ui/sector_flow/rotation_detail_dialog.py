"""板块近 N 日资金明细弹窗。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtGui, QtWidgets

from vnpy_ashare.domain.market.sector_flow import SectorFlowRotationRow
from vnpy_ashare.ui.sector_flow.mini_bar import SectorFlowMiniBar
from vnpy_common.ui.data_table import configure_data_table
from vnpy_common.ui.dialog_shell import apply_standard_dialog_layout, build_panel_footer, setup_responsive_dialog
from vnpy_common.ui.panel_widgets import panel_status_label, section_title
from vnpy_common.ui.theme.manager import theme_manager
from vnpy_common.ui.theme.market_colors import pct_change_color


def _format_trade_date_label(trade_date: str) -> str:
    cleaned = str(trade_date or "").strip()
    if len(cleaned) == 8 and cleaned.isdigit():
        return f"{cleaned[:4]}-{cleaned[4:6]}-{cleaned[6:8]}"
    return cleaned


class SectorFlowRotationDetailDialog(QtWidgets.QDialog):
    """展示单板块近 N 日主力净流入明细。"""

    market_drilldown_requested = QtCore.Signal(object)

    def __init__(
        self,
        rotation_row: SectorFlowRotationRow,
        *,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._rotation_row = rotation_row
        sector = rotation_row.sector
        self.setObjectName("SectorFlowRotationDetailDialog")
        self.setWindowTitle(f"{sector.name} · 资金明细")

        setup_responsive_dialog(
            self,
            parent,
            min_width=520,
            min_height=460,
            width_ratio=0.42,
            height_ratio=0.55,
            max_width=720,
            max_height=640,
        )

        summary = panel_status_label(
            f"涨幅 {sector.change_pct:+.2f}% · 当日主力 {sector.net_flow_yi:+.2f}亿 · "
            f"{rotation_row.flow_pattern} · 15日累计 {rotation_row.cumulative_net_yi:+.1f}亿 · "
            f"动量Δ {rotation_row.momentum_delta:+.1f}亿 · 净流入 {rotation_row.positive_days} 天"
        )

        chart_label = section_title("近15日主力净流入（亿）")
        self._mini_bar = SectorFlowMiniBar(self, max_points=15)
        self._mini_bar.setMinimumHeight(96)
        self._mini_bar.render_points(list(rotation_row.points))

        self._table = QtWidgets.QTableWidget(0, 2)
        configure_data_table(self._table)
        self._table.setHorizontalHeaderLabels(["交易日", "主力净流入(亿)"])
        self._table.setColumnWidth(0, 120)
        self._fill_table(rotation_row)

        content = QtWidgets.QWidget(self)
        content_layout = QtWidgets.QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(10)
        content_layout.addWidget(summary)
        content_layout.addWidget(chart_label)
        content_layout.addWidget(self._mini_bar)
        content_layout.addWidget(section_title("日明细"))
        content_layout.addWidget(self._table, stretch=1)

        close_btn = QtWidgets.QPushButton("关闭")
        close_btn.setObjectName("SecondaryButton")
        close_btn.clicked.connect(self.reject)
        market_btn = QtWidgets.QPushButton("市场成分")
        market_btn.setObjectName("ActionButton")
        market_btn.clicked.connect(self._emit_market_drilldown)
        footer = build_panel_footer(panel_status_label(""), close_btn, (market_btn, 0))

        apply_standard_dialog_layout(self, content=content, footer=footer)
        theme_manager().register_callback(lambda _t: self._table.viewport().update())

    def _fill_table(self, rotation_row: SectorFlowRotationRow) -> None:
        points = list(rotation_row.points)
        self._table.setRowCount(len(points))
        tokens = theme_manager().tokens()
        for row_index, point in enumerate(reversed(points)):
            date_item = QtWidgets.QTableWidgetItem(_format_trade_date_label(point.trade_date))
            flow_item = QtWidgets.QTableWidgetItem(f"{point.net_flow_yi:+.2f}")
            flow_item.setTextAlignment(int(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter))
            flow_item.setForeground(QtGui.QColor(pct_change_color(point.net_flow_yi, tokens)))
            self._table.setItem(row_index, 0, date_item)
            self._table.setItem(row_index, 1, flow_item)
        self._table.resizeColumnsToContents()

    def _emit_market_drilldown(self) -> None:
        self.market_drilldown_requested.emit(self._rotation_row.sector)
        self.accept()
