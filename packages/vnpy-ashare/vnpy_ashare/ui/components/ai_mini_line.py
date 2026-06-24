"""AI 聊天内嵌迷你折线图。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtGui, QtWidgets

from vnpy_common.ai.protocol import AiChartBar, AiChartSpec
from vnpy_common.ui.theme.manager import theme_manager

_TOP = 8
_LABEL_HEIGHT = 14


def _line_color(overlays: list[dict[str, object]]) -> str:
    for item in overlays:
        if not isinstance(item, dict):
            continue
        if str(item.get("kind") or "") != "line_style":
            continue
        color = str(item.get("color") or "").strip()
        if color:
            return color
    return "#5b9cf5"


class AiMiniLineChart(QtWidgets.QWidget):
    """单序列折线（回测权益、指标趋势等）。"""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("AiMiniLineChart")
        self._points: list[AiChartBar] = []
        self._line_color = "#5b9cf5"
        self.setMinimumHeight(132)
        self.setMaximumHeight(132)
        theme_manager().register_callback(lambda _tokens: self.update())

    def render_spec(self, spec: AiChartSpec) -> None:
        self._points = list(spec.series)
        self._line_color = _line_color(list(spec.overlays))
        self.update()

    def clear(self) -> None:
        self._points = []
        self.update()

    def paintEvent(self, _event: QtGui.QPaintEvent) -> None:
        super().paintEvent(_event)
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        tokens = theme_manager().tokens()
        painter.fillRect(self.rect(), QtGui.QColor(tokens.depth_bg))

        if not self._points:
            painter.setPen(QtGui.QColor(tokens.text_muted))
            painter.drawText(self.rect(), int(QtCore.Qt.AlignmentFlag.AlignCenter), "暂无折线数据")
            painter.end()
            return

        left = 8
        right = max(self.width() - 8, left + 40)
        width = right - left
        bottom = self.height() - _LABEL_HEIGHT - 8
        top = _TOP
        chart_height = max(bottom - top, 20)

        values = [point.close for point in self._points]
        value_min = min(values)
        value_max = max(values)
        if value_max <= value_min:
            value_max = value_min + 1.0
        pad = (value_max - value_min) * 0.08
        value_min -= pad
        value_max += pad

        def value_y(value: float) -> float:
            ratio = (value - value_min) / (value_max - value_min)
            return bottom - ratio * chart_height

        painter.setPen(QtGui.QPen(QtGui.QColor(tokens.panel_border), 1))
        painter.drawLine(int(left), int(bottom), int(right), int(bottom))

        count = len(self._points)
        gap = 0 if count <= 1 else width / (count - 1)
        line_pen = QtGui.QPen(QtGui.QColor(self._line_color), 1.5)
        painter.setPen(line_pen)
        path = QtGui.QPainterPath()
        started = False
        for index, point in enumerate(self._points):
            x = left if count <= 1 else left + gap * index
            y = value_y(point.close)
            if not started:
                path.moveTo(x, y)
                started = True
            else:
                path.lineTo(x, y)
        painter.drawPath(path)

        if len(self._points) >= 2:
            first = self._points[0].close
            last = self._points[-1].close
            delta = last - first
            pct = (delta / first * 100) if first else 0.0
            color = QtGui.QColor(tokens.market_rise if delta >= 0 else tokens.market_fall)
            painter.setPen(color)
            painter.drawText(
                QtCore.QRectF(left, top - 2, width, 14),
                int(QtCore.Qt.AlignmentFlag.AlignRight),
                f"{last:,.2f} ({pct:+.2f}%)",
            )

        painter.setPen(QtGui.QColor(tokens.text_muted))
        first_date = self._points[0].date
        last_date = self._points[-1].date
        painter.drawText(
            QtCore.QRectF(left, bottom + 2, width / 2, _LABEL_HEIGHT),
            int(QtCore.Qt.AlignmentFlag.AlignLeft),
            first_date[-5:] if len(first_date) >= 5 else first_date,
        )
        painter.drawText(
            QtCore.QRectF(left + width / 2, bottom + 2, width / 2, _LABEL_HEIGHT),
            int(QtCore.Qt.AlignmentFlag.AlignRight),
            last_date[-5:] if len(last_date) >= 5 else last_date,
        )
        painter.end()
