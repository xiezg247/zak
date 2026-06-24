"""迷你图画廊（笔记中心 / 可复用）。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtGui, QtWidgets

from vnpy_common.ai.protocol import AiChartSpec
from vnpy_common.ui.theme.manager import theme_manager


def create_ai_chart_widget(spec: AiChartSpec, parent: QtWidgets.QWidget) -> QtWidgets.QWidget:
    if spec.kind == "line":
        from vnpy_ashare.ui.components.ai_mini_line import AiMiniLineChart

        chart = AiMiniLineChart(parent)
    else:
        from vnpy_ashare.ui.components.ai_mini_candle import AiMiniCandleChart

        chart = AiMiniCandleChart(parent)
    chart.render_spec(spec)
    return chart


def chart_gallery_stylesheet(tokens) -> str:
    return f"""
QFrame#AiMiniChartPanel {{
    background-color: {tokens.screener_log_bg};
    border: 1px solid {tokens.panel_border};
    border-radius: 8px;
}}
QLabel#AiMiniChartCaption {{
    color: {tokens.text_primary};
    font-size: 12px;
}}
QLabel#AiMiniChartHint {{
    color: {tokens.text_secondary};
    font-size: 11px;
}}
QWidget#AiMiniCandleChart,
QWidget#AiMiniLineChart {{
    background-color: {tokens.depth_bg};
    border-radius: 4px;
}}
"""


class AiMiniChartPanel(QtWidgets.QFrame):
    """单张迷你图卡片（无 LLM 依赖）。"""

    clicked = QtCore.Signal(str, str)

    def __init__(
        self,
        spec: AiChartSpec,
        *,
        hint: str = "点击查看个股分析 →",
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._spec = spec
        self.setObjectName("AiMiniChartPanel")
        self.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
        theme_manager().bind_stylesheet(self, extra=chart_gallery_stylesheet)

        caption = spec.caption or spec.symbol
        caption_label = QtWidgets.QLabel(caption)
        caption_label.setObjectName("AiMiniChartCaption")
        chart = create_ai_chart_widget(spec, self)
        hint_label = QtWidgets.QLabel(hint)
        hint_label.setObjectName("AiMiniChartHint")

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)
        layout.addWidget(caption_label)
        layout.addWidget(chart)
        layout.addWidget(hint_label)

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.clicked.emit(self._spec.symbol, self._spec.name)
            event.accept()
            return
        super().mousePressEvent(event)

    def sync_width(self, width: int) -> None:
        width = max(220, width)
        self.setMinimumWidth(width)
        self.setMaximumWidth(width)


class AiChartGallery(QtWidgets.QWidget):
    """垂直排列的多张迷你图。"""

    symbol_clicked = QtCore.Signal(str, str)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("AiChartGallery")
        self._layout = QtWidgets.QVBoxLayout(self)
        self._layout.setContentsMargins(0, 8, 0, 0)
        self._layout.setSpacing(8)
        self._panels: list[AiMiniChartPanel] = []

    def render_specs(self, specs: list[AiChartSpec]) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._panels.clear()
        for spec in specs:
            panel = AiMiniChartPanel(spec, parent=self)
            panel.clicked.connect(self.symbol_clicked.emit)
            self._panels.append(panel)
            self._layout.addWidget(panel)
        self.setVisible(bool(specs))

    def sync_width(self, width: int) -> None:
        for panel in self._panels:
            panel.sync_width(width)

    def clear(self) -> None:
        self.render_specs([])
