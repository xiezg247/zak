"""板块未来 N 日展望明细弹窗。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.domain.market.sector_flow import (
    SectorFlowOutlookCompareRow,
    SectorFlowOutlookRow,
)
from vnpy_common.ui.dialog_shell import apply_standard_dialog_layout, build_panel_footer, setup_responsive_dialog
from vnpy_common.ui.panel_widgets import panel_status_label, section_title


def _format_trade_date_label(trade_date: str) -> str:
    cleaned = str(trade_date or "").strip()
    if len(cleaned) == 8 and cleaned.isdigit():
        return f"{cleaned[:4]}-{cleaned[4:6]}-{cleaned[6:8]}"
    return cleaned


class SectorFlowOutlookDetailDialog(QtWidgets.QDialog):
    market_drilldown_requested = QtCore.Signal(object)

    def __init__(
        self,
        payload: SectorFlowOutlookRow | SectorFlowOutlookCompareRow,
        *,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._payload = payload
        if isinstance(payload, SectorFlowOutlookCompareRow):
            sector = payload.sector
            title_suffix = "对照明细"
        else:
            sector = payload.sector
            title_suffix = "展望明细"
        self.setObjectName("SectorFlowOutlookDetailDialog")
        self.setWindowTitle(f"{sector.name} · {title_suffix}")

        setup_responsive_dialog(
            self,
            parent,
            min_width=480,
            min_height=360,
            width_ratio=0.38,
            height_ratio=0.45,
            max_width=640,
            max_height=520,
        )

        summary = panel_status_label(self._build_summary_text())
        self._table = QtWidgets.QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["口径", "交易日", "标签", "强度"])
        self._table.horizontalHeader().setStretchLastSection(True)
        self._fill_table()

        content = QtWidgets.QWidget(self)
        layout = QtWidgets.QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        layout.addWidget(summary)
        layout.addWidget(section_title("未来3日标签"))
        layout.addWidget(self._table, stretch=1)

        close_btn = QtWidgets.QPushButton("关闭")
        close_btn.setObjectName("SecondaryButton")
        close_btn.clicked.connect(self.reject)
        market_btn = QtWidgets.QPushButton("市场成分")
        market_btn.setObjectName("ActionButton")
        market_btn.clicked.connect(lambda: self.market_drilldown_requested.emit(sector))
        footer = build_panel_footer(panel_status_label("统计情景，非资金预测"), close_btn, (market_btn, 0))
        apply_standard_dialog_layout(self, content=content, footer=footer)

    def _build_summary_text(self) -> str:
        payload = self._payload
        if isinstance(payload, SectorFlowOutlookCompareRow):
            cont = payload.continuation.rationale if payload.continuation else "—"
            strat = payload.strategy.rationale if payload.strategy else "—"
            return f"一致性 {payload.agreement} · 延续：{cont} · 策略：{strat}"
        return f"{payload.headline_pattern} · {payload.rationale}"

    def _fill_table(self) -> None:
        rows: list[tuple[str, str, str, str]] = []
        payload = self._payload
        if isinstance(payload, SectorFlowOutlookCompareRow):
            if payload.continuation:
                for day in payload.continuation.days:
                    rows.append(("延续", _format_trade_date_label(day.trade_date), day.bias, f"{day.strength:.2f}"))
            if payload.strategy:
                for day in payload.strategy.days:
                    rows.append(("策略", _format_trade_date_label(day.trade_date), day.bias, f"{day.strength:.2f}"))
        else:
            source_label = "延续" if payload.source == "continuation" else "策略"
            for day in payload.days:
                rows.append((source_label, _format_trade_date_label(day.trade_date), day.bias, f"{day.strength:.2f}"))
        self._table.setRowCount(len(rows))
        for row_index, cells in enumerate(rows):
            for col_index, text in enumerate(cells):
                item = QtWidgets.QTableWidgetItem(text)
                item.setFlags(item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
                self._table.setItem(row_index, col_index, item)
