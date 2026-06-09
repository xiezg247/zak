"""K 线均线图例说明。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.ui.ma_line_item import MA_LINE_SPECS

MA_COLOR_NAMES: tuple[str, ...] = ("黄色", "蓝色", "紫色")


class MaLegendBar(QtWidgets.QWidget):
    """图表上方 MA 颜色说明。"""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("MaLegendBar")

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(8, 3, 8, 3)
        layout.setSpacing(14)

        for (_period, color, label), color_name in zip(MA_LINE_SPECS, MA_COLOR_NAMES, strict=True):
            item = QtWidgets.QLabel(f'<span style="color:{color}; font-weight:600;">{label}</span><span style="color:#888888;">（{color_name}）</span>')
            item.setTextFormat(QtCore.Qt.TextFormat.RichText)
            layout.addWidget(item)

        layout.addStretch()
