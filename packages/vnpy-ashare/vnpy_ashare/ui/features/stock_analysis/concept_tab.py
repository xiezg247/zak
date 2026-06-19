"""个股分析：概念/题材 Tab。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.services.stock.concept import ConceptProfile
from vnpy_common.ui.data_table import configure_data_table
from vnpy_common.ui.panel_widgets import MetricTile, content_card, hint_label, section_title, tab_page


class ConceptAnalysisTab(QtWidgets.QWidget):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._status = hint_label("")
        self._count_tile = MetricTile("所属概念", subtitle="同花顺")

        self._table = QtWidgets.QTableWidget(0, 2)
        self._table.setHorizontalHeaderLabels(["概念名称", "概念 ID"])
        configure_data_table(self._table)
        self._table.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Expanding,
        )

        metrics = QtWidgets.QHBoxLayout()
        metrics.addWidget(self._count_tile, stretch=1)
        metrics_wrap = QtWidgets.QWidget()
        metrics_wrap.setLayout(metrics)

        page = tab_page(
            self._status,
            content_card(metrics_wrap, margins=(8, 8, 8, 8)),
            content_card(section_title("概念列表"), self._table),
            stretch_index=2,
        )
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(page)

    def show_idle(self, message: str = "切换到本 Tab 时加载概念题材") -> None:
        self._status.setText(message)
        self._count_tile.set_value("—")
        self._table.setRowCount(0)

    def show_loading(self, message: str = "正在加载概念题材…") -> None:
        self._status.setText(message)
        self._count_tile.set_value("…")
        self._table.setRowCount(0)

    def show_profile(self, profile: ConceptProfile | None) -> None:
        if profile is None:
            self._status.setText("暂无概念数据")
            self._count_tile.set_value("—")
            self._table.setRowCount(0)
            return

        concepts = profile.concepts
        self._count_tile.set_value(str(len(concepts)), subtitle="个概念")
        if profile.message and not concepts:
            self._status.setText(profile.message)
        else:
            self._status.setText(profile.message or f"共 {len(concepts)} 个概念板块")

        self._table.setRowCount(len(concepts))
        for row_idx, row in enumerate(concepts):
            values = [
                str(row.get("concept_name") or ""),
                str(row.get("concept_id") or ""),
            ]
            for col_idx, text in enumerate(values):
                item = QtWidgets.QTableWidgetItem(text)
                item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
                self._table.setItem(row_idx, col_idx, item)
        self._table.resizeColumnsToContents()
