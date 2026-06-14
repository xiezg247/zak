"""主窗口左侧图标 + 文字导航栏。"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from vnpy.trader.ui import QtCore, QtGui, QtWidgets

from vnpy_ashare.ui.styles import ACCENT_COLOR, NAV_MUTED_COLOR

if TYPE_CHECKING:
    from vnpy_common.ui.theme import ThemeTokens


@dataclass(frozen=True)
class NavEntry:
    key: str
    label: str


@dataclass(frozen=True)
class NavGroup:
    entries: tuple[NavEntry, ...]


# 主窗口左侧菜单（自选首页；组间以分隔线区分）
APP_NAV_GROUPS: tuple[NavGroup, ...] = (
    NavGroup(
        (
            NavEntry("watchlist", "自选"),
            NavEntry("market", "市场"),
            NavEntry("sector_flow", "板块资金"),
            NavEntry("radar", "雷达"),
            NavEntry("local", "本地"),
        ),
    ),
    NavGroup(
        (NavEntry("screener", "选股"),),
    ),
    NavGroup((NavEntry("ai_assistant", "AI 助手"),)),
    NavGroup(
        (
            NavEntry("cta_backtest", "策略回测"),
            NavEntry("batch_backtest", "回测对比"),
        ),
    ),
)

APP_NAV_ENTRIES: tuple[NavEntry, ...] = tuple(entry for group in APP_NAV_GROUPS for entry in group.entries)

# 菜单栏「后台」入口（不在侧栏展示）
BACKSTAGE_ENTRIES: tuple[NavEntry, ...] = (
    NavEntry("scheduler", "定时任务"),
    NavEntry("data_manager", "数据管理"),
)

BACKSTAGE_PAGE_KEYS: frozenset[str] = frozenset(entry.key for entry in BACKSTAGE_ENTRIES)

NAV_SHORTCUTS: dict[str, str] = {
    "watchlist": "Ctrl+1",
    "market": "Ctrl+2",
    "sector_flow": "Ctrl+3",
    "radar": "Ctrl+4",
    "local": "Ctrl+5",
    "screener": "Ctrl+6",
    "ai_assistant": "Ctrl+7",
    "cta_backtest": "Ctrl+8",
    "batch_backtest": "Ctrl+9",
}

BACKSTAGE_SHORTCUTS: dict[str, str] = {
    "scheduler": "Ctrl+0",
}


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


def _draw_scheduler(painter: QtGui.QPainter, size: int) -> None:
    m = 4
    painter.drawEllipse(m + 1, m + 1, size - m * 2 - 2, size - m * 2 - 2)
    painter.drawLine(size // 2, size // 2, size // 2, m + 8)
    painter.drawLine(size // 2, size // 2, size - m - 6, size // 2 + 3)


def _draw_data(painter: QtGui.QPainter, size: int) -> None:
    m = 5
    w = size - m * 2
    painter.drawEllipse(m, m, w, 6)
    painter.drawLine(m, m + 3, m, m + 14)
    painter.drawLine(m + w, m + 3, m + w, m + 14)
    painter.drawEllipse(m, m + 10, w, 6)


def _draw_ai_assistant(painter: QtGui.QPainter, size: int) -> None:
    m = 4
    rect = QtCore.QRectF(m + 1, m + 3, size - m * 2 - 2, size - m * 2 - 4)
    painter.drawRoundedRect(rect, 4, 4)
    painter.drawLine(m + 7, m + 11, m + 11, m + 15)
    painter.drawLine(m + 11, m + 15, m + 17, m + 9)
    tail = QtGui.QPolygonF(
        [
            QtCore.QPointF(m + 8, size - m - 3),
            QtCore.QPointF(m + 4, size - m + 1),
            QtCore.QPointF(m + 12, size - m - 2),
        ]
    )
    painter.drawPolyline(tail)


def _draw_auto_screener(painter: QtGui.QPainter, size: int) -> None:
    m = 5
    painter.drawEllipse(m, m, size - m * 2 - 2, size - m * 2 - 2)
    painter.drawLine(size // 2, m + 6, size // 2, size - m - 6)
    painter.drawLine(m + 6, size // 2, size - m - 6, size // 2)


def _draw_screener(painter: QtGui.QPainter, size: int) -> None:
    m = 5
    path = QtGui.QPainterPath()
    path.moveTo(m, m + 2)
    path.lineTo(size - m, m + 2)
    path.lineTo(size - m - 4, size // 2 + 2)
    path.lineTo(size // 2 + 2, size // 2 + 2)
    path.lineTo(size // 2 - 2, size - m - 1)
    path.lineTo(m + 4, size // 2 + 2)
    path.lineTo(m, size // 2 + 2)
    path.closeSubpath()
    painter.drawPath(path)


def _draw_batch_backtest(painter: QtGui.QPainter, size: int) -> None:
    m = 4
    painter.drawRect(m, m + 2, size - m * 2 - 8, size - m * 2 - 6)
    painter.drawRect(m + 10, m + 4, size - m * 2 - 8, size - m * 2 - 6)
    for offset in (0, 8, 16):
        painter.drawLine(m + 3 + offset, size - m - 4, m + 8 + offset, size - m - 10)


def _draw_sector_flow(painter: QtGui.QPainter, size: int) -> None:
    m = 4
    painter.drawRect(m, m + 8, size - 2 * m, size - m - 8)
    for x_offset in (6, 12, 18):
        painter.drawLine(m + x_offset, size - m - 4, m + x_offset, m + 12 + (x_offset % 6))


def _draw_radar(painter: QtGui.QPainter, size: int) -> None:
    m = 5
    for index, _offset in enumerate((0, 8, 16)):
        y = m + 2 + index * 6
        painter.drawLine(m, y, size - m - 6, y)
        painter.drawLine(size - m - 4, y - 1, size - m - 4, y + 1)


_ICON_DRAWERS: dict[str, Callable[[QtGui.QPainter, int], None]] = {
    "market": _draw_market,
    "sector_flow": _draw_sector_flow,
    "radar": _draw_radar,
    "watchlist": _draw_watchlist,
    "screener": _draw_screener,
    "auto_screener": _draw_auto_screener,
    "local": _draw_local,
    "cta_backtest": _draw_backtest,
    "batch_backtest": _draw_batch_backtest,
    "scheduler": _draw_scheduler,
    "data_manager": _draw_data,
    "ai_assistant": _draw_ai_assistant,
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
        shortcut = NAV_SHORTCUTS.get(entry.key, "")
        if shortcut:
            self.setToolTip(f"{entry.label}（{shortcut}）")
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


class NavGroupSpacer(QtWidgets.QWidget):
    """组间留白，中心绘制短分隔线（避免 QFrame.HLine 原生通栏线）。"""

    _LINE_WIDTH = 28

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("NavGroupSpacer")
        self.setFixedHeight(14)
        self._line_color = QtGui.QColor(NAV_MUTED_COLOR)
        self._line_color.setAlpha(72)

    def set_line_color(self, color: QtGui.QColor) -> None:
        self._line_color = color
        self.update()

    def paintEvent(self, _event: QtGui.QPaintEvent) -> None:
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        line_width = min(self._LINE_WIDTH, max(0, self.width() - 16))
        if line_width <= 0:
            return
        x = (self.width() - line_width) // 2
        y = self.height() // 2
        pen = QtGui.QPen(self._line_color)
        pen.setWidthF(1.0)
        pen.setCapStyle(QtCore.Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawLine(x, y, x + line_width, y)


class SidebarNav(QtWidgets.QWidget):
    """主窗口左侧垂直导航。"""

    page_changed = QtCore.Signal(int)

    DEFAULT_WIDTH = 72
    MIN_WIDTH = 64
    MAX_WIDTH = 140

    def __init__(
        self,
        groups: tuple[NavGroup, ...] = APP_NAV_GROUPS,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("SidebarNav")
        self.setMinimumWidth(self.MIN_WIDTH)
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Expanding,
        )
        self._entries = tuple(entry for group in groups for entry in group.entries)

        self._scroll = QtWidgets.QScrollArea()
        self._scroll.setObjectName("NavScroll")
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self._scroll.setAutoFillBackground(True)
        self._scroll.viewport().setAutoFillBackground(True)

        nav_body = QtWidgets.QWidget()
        nav_body.setObjectName("NavBody")
        layout = QtWidgets.QVBoxLayout(nav_body)
        layout.setContentsMargins(0, 8, 0, 8)
        layout.setSpacing(4)

        self._group = QtWidgets.QButtonGroup(self)
        self._group.setExclusive(True)
        self._buttons: list[NavButton] = []
        self._spacers: list[NavGroupSpacer] = []

        index = 0
        for group_index, group in enumerate(groups):
            for entry in group.entries:
                btn = NavButton(entry, nav_body)
                btn.clicked.connect(lambda checked, i=index: self._on_click(i))
                self._group.addButton(btn, index)
                layout.addWidget(btn)
                self._buttons.append(btn)
                index += 1

            if group_index < len(groups) - 1:
                spacer = NavGroupSpacer(nav_body)
                layout.addWidget(spacer)
                self._spacers.append(spacer)

        layout.addStretch()
        self._scroll.setWidget(nav_body)

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._scroll, stretch=1)

        self.refresh_theme()

    def refresh_theme(self, tokens: ThemeTokens | None = None) -> None:
        if tokens is None:
            from vnpy_common.ui.theme import theme_manager

            tokens = theme_manager().tokens()
        nav_bg = tokens.nav_bg
        self._scroll.setStyleSheet(
            f"QScrollArea#NavScroll {{ border: none; background-color: {nav_bg}; }}",
        )
        self._scroll.viewport().setStyleSheet(f"background-color: {nav_bg};")
        palette = self._scroll.viewport().palette()
        palette.setColor(self._scroll.viewport().backgroundRole(), QtGui.QColor(nav_bg))
        self._scroll.viewport().setPalette(palette)
        for btn in self._buttons:
            btn._muted = QtGui.QColor(tokens.nav_muted)
            btn._accent = QtGui.QColor(tokens.accent)
            btn._update_icon(btn.isChecked())
        line_color = QtGui.QColor(tokens.nav_muted)
        line_color.setAlpha(72)
        for spacer in self._spacers:
            spacer.set_line_color(line_color)

    def _on_click(self, index: int) -> None:
        self.set_active_index(index)
        self.page_changed.emit(index)

    def set_active_index(self, index: int) -> None:
        for i, btn in enumerate(self._buttons):
            btn.set_active(i == index)

    def clear_active(self) -> None:
        """后台页等非侧栏页面：取消侧栏选中态。"""
        self._group.setExclusive(False)
        for btn in self._buttons:
            btn.setChecked(False)
            btn.set_active(False)
        self._group.setExclusive(True)

    def entry_at(self, index: int) -> NavEntry:
        return self._entries[index]
