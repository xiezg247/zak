"""主窗口左侧图标 + 文字导航栏。"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from vnpy.trader.ui import QtCore, QtGui, QtWidgets

from vnpy_ashare.ui.styles import ACCENT_COLOR, NAV_MUTED_COLOR


@dataclass(frozen=True)
class NavEntry:
    key: str
    label: str


# 主窗口左侧菜单（自选首页，市场用于搜索发现）
APP_NAV_ENTRIES: tuple[NavEntry, ...] = (
    NavEntry("watchlist", "自选"),
    NavEntry("market", "市场"),
    NavEntry("local", "本地"),
    NavEntry("cta_backtest", "策略回测"),
    NavEntry("data_manager", "数据管理"),
)


def _tinted_icon(
    draw: Callable[[QtGui.QPainter, int], None],
    color: QtGui.QColor,
    size: int = 28,
) -> QtGui.QIcon:
    pixmap = QtGui.QPixmap(size, size)
    pixmap.fill(QtCore.Qt.GlobalColor.transparent)
    painter = QtGui.QPainter(pixmap)
    painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
    pen = QtGui.QPen(color, 1.8)
    pen.setCapStyle(QtCore.Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(QtCore.Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
    draw(painter, size)
    painter.end()
    return QtGui.QIcon(pixmap)


def _draw_market(painter: QtGui.QPainter, size: int) -> None:
    m = 3
    painter.drawRoundedRect(m, m + 2, size - m * 2, size - m * 2 - 4, 2, 2)
    pts = [
        QtCore.QPointF(m + 4, size - m - 6),
        QtCore.QPointF(m + 10, size - m - 12),
        QtCore.QPointF(m + 16, size - m - 9),
        QtCore.QPointF(size - m - 4, m + 8),
    ]
    painter.drawPolyline(QtGui.QPolygonF(pts))


def _draw_watchlist(painter: QtGui.QPainter, size: int) -> None:
    m = 4
    path = QtGui.QPainterPath()
    path.moveTo(size // 2, m + 2)
    path.lineTo(size - m - 2, m + 8)
    path.lineTo(size - m - 2, size - m - 2)
    path.lineTo(m + 2, size - m - 2)
    path.lineTo(m + 2, m + 8)
    path.closeSubpath()
    painter.drawPath(path)
    painter.drawLine(size // 2 - 4, size // 2, size // 2 + 4, size // 2)
    painter.drawLine(size // 2, size // 2 - 4, size // 2, size // 2 + 4)


def _draw_local(painter: QtGui.QPainter, size: int) -> None:
    m = 4
    painter.drawRoundedRect(m + 2, m + 6, size - m * 2 - 4, size - m - 8, 2, 2)
    painter.drawLine(m + 8, m + 2, m + 8, m + 8)
    painter.drawLine(m + 8, m + 2, size - m - 6, m + 2)
    painter.drawLine(size // 2 - 5, size // 2 + 2, size // 2 + 5, size // 2 + 2)
    painter.drawLine(size // 2, size // 2 - 3, size // 2, size // 2 + 7)


def _draw_backtest(painter: QtGui.QPainter, size: int) -> None:
    m = 4
    painter.drawRect(m, m + 4, size - m * 2, size - m * 2 - 4)
    pts = [
        QtCore.QPointF(m + 3, size - m - 5),
        QtCore.QPointF(m + 10, size - m - 11),
        QtCore.QPointF(m + 17, size - m - 8),
        QtCore.QPointF(size - m - 3, m + 7),
    ]
    painter.drawPolyline(QtGui.QPolygonF(pts))


def _draw_data(painter: QtGui.QPainter, size: int) -> None:
    m = 5
    w = size - m * 2
    painter.drawEllipse(m, m, w, 6)
    painter.drawLine(m, m + 3, m, m + 14)
    painter.drawLine(m + w, m + 3, m + w, m + 14)
    painter.drawEllipse(m, m + 10, w, 6)


_ICON_DRAWERS: dict[str, Callable[[QtGui.QPainter, int], None]] = {
    "market": _draw_market,
    "watchlist": _draw_watchlist,
    "local": _draw_local,
    "cta_backtest": _draw_backtest,
    "data_manager": _draw_data,
}


class NavButton(QtWidgets.QToolButton):
    def __init__(self, entry: NavEntry, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.entry = entry
        self.setObjectName("NavButton")
        self.setCheckable(True)
        self.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.setIconSize(QtCore.QSize(28, 28))
        self.setText(entry.label)
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Fixed,
        )
        self._muted = QtGui.QColor(NAV_MUTED_COLOR)
        self._accent = QtGui.QColor(ACCENT_COLOR)
        self._update_icon(False)

    def _update_icon(self, active: bool) -> None:
        color = self._accent if active else self._muted
        draw = _ICON_DRAWERS[self.entry.key]
        self.setIcon(_tinted_icon(draw, color))

    def set_active(self, active: bool) -> None:
        self.setChecked(active)
        self._update_icon(active)


class SidebarNav(QtWidgets.QWidget):
    """主窗口左侧垂直导航。"""

    page_changed = QtCore.Signal(int)

    def __init__(
        self,
        entries: tuple[NavEntry, ...] = APP_NAV_ENTRIES,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("SidebarNav")
        self.setFixedWidth(72)
        self._entries = entries

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 16, 0, 16)
        layout.setSpacing(4)

        self._group = QtWidgets.QButtonGroup(self)
        self._group.setExclusive(True)
        self._buttons: list[NavButton] = []

        for index, entry in enumerate(entries):
            btn = NavButton(entry, self)
            btn.clicked.connect(lambda checked, i=index: self._on_click(i))
            self._group.addButton(btn, index)
            layout.addWidget(btn)
            self._buttons.append(btn)

            if entry.key == "local":
                line = QtWidgets.QFrame()
                line.setFrameShape(QtWidgets.QFrame.Shape.HLine)
                line.setStyleSheet("background-color: #2a2a30; max-height: 1px; margin: 8px 10px;")
                layout.addWidget(line)

        layout.addStretch()

    def _on_click(self, index: int) -> None:
        self.set_active_index(index)
        self.page_changed.emit(index)

    def set_active_index(self, index: int) -> None:
        for i, btn in enumerate(self._buttons):
            btn.set_active(i == index)

    def entry_at(self, index: int) -> NavEntry:
        return self._entries[index]
