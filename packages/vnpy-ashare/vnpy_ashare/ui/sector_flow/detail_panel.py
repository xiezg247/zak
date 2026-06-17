"""板块详情侧栏：成分龙头。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtGui, QtWidgets

from vnpy_ashare.domain.market.sector_flow import SectorConstituentRow, SectorFlowHistoryPoint, SectorFlowRow
from vnpy_ashare.ui.sector_flow.mini_bar import SectorFlowMiniBar
from vnpy_common.ui.loading_overlay import ContentLoadingOverlay
from vnpy_common.ui.theme import theme_manager
from vnpy_common.ui.theme.market_colors import pct_change_color

_HEADERS = ("名称", "涨幅%", "主力(万)")


class SectorFlowDetailPanel(QtWidgets.QFrame):
    """选中板块的摘要、近 5 日资金与成分龙头。"""

    market_drilldown_requested = QtCore.Signal(object)
    screener_requested = QtCore.Signal(str)
    resonance_screener_requested = QtCore.Signal()

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("SectorFlowDetailPanel")
        self.setMinimumWidth(220)
        self._current_sector: SectorFlowRow | None = None

        self._title = QtWidgets.QLabel("板块详情")
        self._title.setObjectName("SectionLabel")
        self._summary = QtWidgets.QLabel("选中左侧板块查看成分龙头")
        self._summary.setObjectName("SectorFlowSummary")
        self._summary.setWordWrap(True)

        self._mini_bar = SectorFlowMiniBar(self)

        action_row = QtWidgets.QHBoxLayout()
        action_row.setSpacing(6)
        self._market_btn = QtWidgets.QPushButton("市场成分")
        self._market_btn.setObjectName("SecondaryButton")
        self._market_btn.setToolTip("跳转市场页并按板块成分筛选")
        self._market_btn.clicked.connect(self._emit_market_drilldown)
        self._screener_btn = QtWidgets.QPushButton("成分选股")
        self._screener_btn.setObjectName("SecondaryButton")
        self._screener_btn.setToolTip("对行业成分执行选股")
        self._screener_btn.clicked.connect(self._emit_screener)
        self._resonance_btn = QtWidgets.QPushButton("共振选股")
        self._resonance_btn.setObjectName("SecondaryButton")
        self._resonance_btn.setToolTip("跳转选股页执行雷达共振筛选")
        self._resonance_btn.clicked.connect(self.resonance_screener_requested.emit)
        action_row.addWidget(self._market_btn)
        action_row.addWidget(self._screener_btn)
        action_row.addWidget(self._resonance_btn)

        self._table = QtWidgets.QTableWidget(self)
        self._table.setObjectName("SectorFlowLeaderTable")
        self._table.setColumnCount(len(_HEADERS))
        self._table.setHorizontalHeaderLabels(_HEADERS)
        self._table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        self._table.setAlternatingRowColors(True)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.setColumnWidth(0, 72)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        layout.addWidget(self._title)
        layout.addWidget(self._summary)
        layout.addWidget(self._mini_bar)
        layout.addLayout(action_row)
        layout.addWidget(self._table, stretch=1)

        self._overlay = ContentLoadingOverlay(self)
        self._overlay.hide()

        theme_manager().register_callback(lambda _t: self._table.viewport().update())
        self._sync_action_buttons()

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:
        super().resizeEvent(event)
        self._overlay.setGeometry(self.rect())

    def clear(self) -> None:
        self._overlay.hide_loading()
        self._current_sector = None
        self._summary.setText("选中左侧板块查看成分龙头")
        self._mini_bar.clear()
        self._table.setRowCount(0)
        self._sync_action_buttons()

    def set_loading(self, sector_name: str) -> None:
        self._summary.setText(f"{sector_name} · 加载成分…")
        self._mini_bar.clear()
        self._table.setRowCount(0)
        self._market_btn.setEnabled(False)
        self._screener_btn.setEnabled(False)
        self._resonance_btn.setEnabled(False)
        self._overlay.show_loading("正在加载成分龙头", hint=sector_name)
        self._overlay.setGeometry(self.rect())
        self._overlay.raise_()

    def show_sector(
        self,
        sector: SectorFlowRow,
        leaders: list[SectorConstituentRow],
        *,
        history: list[SectorFlowHistoryPoint] | None = None,
    ) -> None:
        self._overlay.hide_loading()
        self._current_sector = sector
        parts = [
            sector.name,
            f"涨幅 {sector.change_pct:+.2f}%",
            f"主力 {sector.net_flow_yi:+.2f}亿",
        ]
        if sector.divergence_kind:
            parts.append(sector.divergence_kind)
        if sector.leader_stock and not leaders:
            parts.append(f"龙头 {sector.leader_stock}")
        self._summary.setText(" · ".join(parts))
        self._sync_action_buttons()

        if history:
            self._mini_bar.render_points(history)
        else:
            self._mini_bar.clear()

        if not leaders:
            self._table.setRowCount(1)
            hint = QtWidgets.QTableWidgetItem("暂无成分行情（需盘中行情或概念映射）")
            hint.setFlags(QtCore.Qt.ItemFlag.NoItemFlags)
            self._table.setItem(0, 0, hint)
            for col in range(1, len(_HEADERS)):
                self._table.setItem(0, col, QtWidgets.QTableWidgetItem(""))
            return

        self._table.setRowCount(len(leaders))
        tokens = theme_manager().tokens()
        for row_index, leader in enumerate(leaders):
            self._table.setItem(row_index, 0, QtWidgets.QTableWidgetItem(leader.name))
            change_item = QtWidgets.QTableWidgetItem(f"{leader.change_pct:+.2f}")
            change_item.setForeground(QtGui.QColor(pct_change_color(leader.change_pct, tokens)))
            self._table.setItem(row_index, 1, change_item)
            flow_item = QtWidgets.QTableWidgetItem(f"{leader.net_mf_wan:+.0f}" if leader.net_mf_wan else "—")
            if leader.net_mf_wan:
                flow_item.setForeground(QtGui.QColor(pct_change_color(leader.net_mf_wan, tokens)))
            self._table.setItem(row_index, 2, flow_item)

    def _sync_action_buttons(self) -> None:
        sector = self._current_sector
        enabled = sector is not None
        self._market_btn.setEnabled(enabled)
        self._resonance_btn.setEnabled(enabled)
        industry_mode = enabled and sector is not None and sector.sector_kind == "industry"
        self._screener_btn.setEnabled(industry_mode)

    def _emit_market_drilldown(self) -> None:
        if self._current_sector is not None:
            self.market_drilldown_requested.emit(self._current_sector)

    def _emit_screener(self) -> None:
        if self._current_sector is not None:
            self.screener_requested.emit(self._current_sector.name)
