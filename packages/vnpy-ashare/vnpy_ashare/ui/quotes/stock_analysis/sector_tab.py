"""个股分析：板块与估值 Tab。"""

from __future__ import annotations

from typing import Any

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.services.stock_profile_service import SectorProfile, ValuationProfile
from vnpy_ashare.storage.valuation_store import ValuationRow
from vnpy_ashare.ui.quotes.stock_analysis.valuation_sparkline import ValuationHistorySection
from vnpy_common.ui.data_table import configure_data_table
from vnpy_common.ui.panel_widgets import MetricTile, content_card, hint_label, section_title, tab_page


def _fmt_float(value: float | None, *, digits: int = 2, suffix: str = "") -> str:
    if value is None:
        return "—"
    return f"{value:.{digits}f}{suffix}"


class SectorAnalysisTab(QtWidgets.QWidget):
    peer_activated = QtCore.Signal(str, str)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._industry_tile = MetricTile("所属行业")
        self._sector_tile = MetricTile("行业均涨", subtitle="动量排名")
        self._pe_tile = MetricTile("PE (TTM)", subtitle="3年分位")
        self._pb_tile = MetricTile("PB", subtitle="3年分位")
        self._mv_tile = MetricTile("总市值", subtitle="历史样本")

        metrics_row = QtWidgets.QHBoxLayout()
        metrics_row.setSpacing(10)
        for tile in (
            self._industry_tile,
            self._sector_tile,
            self._pe_tile,
            self._pb_tile,
            self._mv_tile,
        ):
            metrics_row.addWidget(tile, stretch=1)

        self._meta_label = hint_label("")
        self._valuation_history = ValuationHistorySection()
        self._disclosure_label = QtWidgets.QLabel("—")
        self._disclosure_label.setWordWrap(True)
        self._disclosure_label.setObjectName("DiagnoseBody")

        self._peer_table = QtWidgets.QTableWidget(0, 5)
        self._peer_table.setHorizontalHeaderLabels(["代码", "名称", "PE(TTM)", "PB", "总市值(亿)"])
        configure_data_table(self._peer_table)
        self._peer_table.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Expanding,
        )
        self._peer_table.cellDoubleClicked.connect(self._on_peer_double_clicked)

        peer_card = content_card(
            section_title("同行业 · 按总市值（双击打开分析）"),
            self._peer_table,
        )
        page = tab_page(
            content_card(self._wrap(metrics_row), margins=(8, 8, 8, 8)),
            self._meta_label,
            self._valuation_history,
            content_card(
                section_title("披露计划"),
                self._disclosure_label,
            ),
            peer_card,
            stretch_index=4,
        )
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(page)

    @staticmethod
    def _wrap(layout: QtWidgets.QLayout) -> QtWidgets.QWidget:
        widget = QtWidgets.QWidget()
        widget.setLayout(layout)
        return widget

    def show_idle(self, message: str = "切换到本 Tab 时加载板块与估值") -> None:
        self._industry_tile.set_value("—")
        self._sector_tile.set_value("—")
        self._pe_tile.set_value("—")
        self._pb_tile.set_value("—")
        self._mv_tile.set_value("—")
        self._meta_label.setText(message)
        self._disclosure_label.setText("—")
        self._peer_table.setRowCount(0)
        self._valuation_history.show_idle(message)

    def show_loading(self, message: str = "正在加载板块与估值…") -> None:
        self._industry_tile.set_value("…")
        self._sector_tile.set_value("…")
        self._pe_tile.set_value("…")
        self._pb_tile.set_value("…")
        self._mv_tile.set_value("…")
        self._meta_label.setText(message)
        self._disclosure_label.setText("—")
        self._peer_table.setRowCount(0)
        self._valuation_history.show_loading()

    def show_profiles(
        self,
        sector: SectorProfile | None,
        valuation: ValuationProfile | None,
        *,
        valuation_history: list[ValuationRow] | None = None,
    ) -> None:
        if sector is None and valuation is None:
            self._industry_tile.set_value("—")
            self._sector_tile.set_value("—")
            self._pe_tile.set_value("—")
            self._pb_tile.set_value("—")
            self._mv_tile.set_value("—")
            self._meta_label.setText("暂无板块数据")
            self._disclosure_label.setText("—")
            self._peer_table.setRowCount(0)
            self._valuation_history.render(valuation_history or [])
            return

        sector = sector or SectorProfile(ts_code="", vt_symbol="", name="")
        valuation = valuation or ValuationProfile(ts_code="", vt_symbol="")

        industry = sector.industry or "—"
        rank_text = f"第 {sector.sector_rank} 名" if sector.sector_rank else "—"
        avg_text = _fmt_float(sector.sector_avg_change_pct, suffix="%")

        self._industry_tile.set_value(industry, subtitle=f"同业 {sector.sector_count or '—'} 只")
        self._sector_tile.set_value(avg_text, subtitle=f"排名 {rank_text}")
        self._pe_tile.set_value(
            _fmt_float(valuation.pe_ttm),
            subtitle=_fmt_float(valuation.pe_percentile_3y, digits=1, suffix="%"),
        )
        self._pb_tile.set_value(
            _fmt_float(valuation.pb),
            subtitle=_fmt_float(valuation.pb_percentile_3y, digits=1, suffix="%"),
        )
        mv_yi = _fmt_float(
            valuation.total_mv / 10000 if valuation.total_mv else None,
            digits=1,
            suffix=" 亿",
        )
        self._mv_tile.set_value(mv_yi, subtitle=f"{valuation.history_days} 日")

        self._meta_label.setText(f"数据日期：{sector.trade_date or '—'}")
        self._valuation_history.render(valuation_history or [])

        if sector.disclosure:
            lines = [f"{row.get('end_date', '—')} · 预约 {row.get('pre_date') or '—'} · 披露 {row.get('ann_date') or '—'}" for row in sector.disclosure]
            self._disclosure_label.setText("\n".join(lines))
        else:
            self._disclosure_label.setText("暂无本地披露计划（打开弹窗或定时任务会同步）")

        self._fill_peers(sector.peers)

    def _fill_peers(self, peers: list[dict[str, Any]]) -> None:
        self._peer_table.setRowCount(len(peers))
        for row_idx, peer in enumerate(peers):
            vt_symbol = str(peer.get("vt_symbol") or "")
            name = str(peer.get("name") or "")
            values = [
                vt_symbol,
                name,
                _fmt_float(peer.get("pe_ttm")),
                _fmt_float(peer.get("pb")),
                _fmt_float(peer.get("total_mv_yi"), digits=1),
            ]
            for col_idx, text in enumerate(values):
                item = QtWidgets.QTableWidgetItem(text)
                item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
                if col_idx == 0:
                    item.setData(QtCore.Qt.ItemDataRole.UserRole, vt_symbol)
                    item.setData(QtCore.Qt.ItemDataRole.UserRole + 1, name)
                self._peer_table.setItem(row_idx, col_idx, item)
        self._peer_table.resizeColumnsToContents()

    def _on_peer_double_clicked(self, row: int, _column: int) -> None:
        item = self._peer_table.item(row, 0)
        if item is None:
            return
        vt_symbol = str(item.data(QtCore.Qt.ItemDataRole.UserRole) or item.text()).strip()
        name = str(item.data(QtCore.Qt.ItemDataRole.UserRole + 1) or "")
        if vt_symbol:
            self.peer_activated.emit(vt_symbol, name)
