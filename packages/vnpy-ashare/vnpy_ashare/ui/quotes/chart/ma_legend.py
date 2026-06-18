"""K 线均线图例说明。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.ui.quotes.chart.ma_line_item import MA_LINE_SPECS
from vnpy_common.ui.theme.manager import theme_manager
from vnpy_common.ui.theme.tokens import ThemeTokens

MA_COLOR_NAMES: tuple[str, ...] = ("黄色", "蓝色", "紫色")


class MaLegendBar(QtWidgets.QWidget):
    """图表上方 MA 颜色说明。"""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("MaLegendBar")
        self._entries: list[tuple[QtWidgets.QLabel, str, str, str]] = []

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(8, 3, 8, 3)
        layout.setSpacing(14)

        for (_period, color, label), color_name in zip(MA_LINE_SPECS, MA_COLOR_NAMES, strict=True):
            item = QtWidgets.QLabel()
            item.setTextFormat(QtCore.Qt.TextFormat.RichText)
            self._entries.append((item, color, label, color_name))
            layout.addWidget(item)

        layout.addStretch()
        self._apply_theme(theme_manager().tokens())
        theme_manager().register_callback(self._apply_theme)

    def _apply_theme(self, tokens: ThemeTokens) -> None:
        for label, color, ma_label, color_name in self._entries:
            label.setText(f'<span style="color:{color}; font-weight:600;">{ma_label}</span><span style="color:{tokens.text_muted};">（{color_name}）</span>')
