"""浮动 AI 按钮与弹出对话面板。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtGui, QtWidgets

from vnpy_llm.engine import LlmEngine
from vnpy_llm.ui.panel import AiChatPanel
from vnpy_llm.ui.styles import PANEL_STYLESHEET

TITLE_BAR_HEIGHT = 36
PANEL_WIDTH = 400
PANEL_HEIGHT = 520

_BTN_SIZE = 48
BTN_MARGIN = 16


class FloatingAiButton(QtWidgets.QPushButton):
    """右下角浮动圆形 AI 按钮。"""

    clicked_toggle = QtCore.Signal()

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("FloatingAiButton")
        self.setFixedSize(_BTN_SIZE, _BTN_SIZE)
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.setToolTip("AI 助手 (Ctrl+L)")
        self.clicked.connect(self.clicked_toggle.emit)
        self.setStyleSheet(
            "QPushButton#FloatingAiButton {"
            "  background-color: #4a9eff;"
            "  border: none;"
            "  border-radius: 24px;"
            "}"
            "QPushButton#FloatingAiButton:hover {"
            "  background-color: #5aadff;"
            "}"
        )

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        super().paintEvent(event)
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)

        m = 10
        pen = QtGui.QPen(QtGui.QColor("#ffffff"), 1.8)
        pen.setCapStyle(QtCore.Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(QtCore.Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)

        rect = QtCore.QRectF(m + 1, m + 3, _BTN_SIZE - m * 2 - 2, _BTN_SIZE - m * 2 - 4)
        painter.drawRoundedRect(rect, 4, 4)
        painter.drawLine(m + 7, m + 11, m + 11, m + 15)
        painter.drawLine(m + 11, m + 15, m + 17, m + 9)
        tail = QtGui.QPolygonF([
            QtCore.QPointF(m + 8, _BTN_SIZE - m - 3),
            QtCore.QPointF(m + 4, _BTN_SIZE - m + 1),
            QtCore.QPointF(m + 12, _BTN_SIZE - m - 2),
        ])
        painter.drawPolyline(tail)
        painter.end()


class FloatingAiPanel(QtWidgets.QWidget):
    """浮动 AI 对话面板（无边框工具窗口）。"""

    expand_requested = QtCore.Signal()
    panel_closed = QtCore.Signal()

    def __init__(
        self,
        engine: LlmEngine,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowFlags(
            QtCore.Qt.WindowType.Tool
            | QtCore.Qt.WindowType.FramelessWindowHint
        )
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_ShowWithoutActivating, False)
        self.setObjectName("FloatingAiPanel")
        self.setMinimumSize(320, 400)
        self.resize(PANEL_WIDTH, PANEL_HEIGHT)

        self._drag_pos: QtCore.QPoint | None = None

        self._build_ui(engine)
        self._restore_geometry()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self, engine: LlmEngine) -> None:
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        title_bar = self._build_title_bar()
        root.addWidget(title_bar)

        self.chat_panel = AiChatPanel(engine, compact=True, parent=self)
        self.chat_panel.expand_requested.connect(self._on_expand)
        root.addWidget(self.chat_panel, stretch=1)

        self.setStyleSheet(_FLOATING_PANEL_STYLESHEET)

        shadow = QtWidgets.QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setColor(QtGui.QColor(0, 0, 0, 80))
        shadow.setOffset(0, 4)
        self.setGraphicsEffect(shadow)

    def _build_title_bar(self) -> QtWidgets.QWidget:
        bar = QtWidgets.QWidget()
        bar.setObjectName("AiFloatingTitleBar")
        bar.setFixedHeight(TITLE_BAR_HEIGHT)
        bar.setCursor(QtCore.Qt.CursorShape.ArrowCursor)

        layout = QtWidgets.QHBoxLayout(bar)
        layout.setContentsMargins(12, 0, 8, 0)
        layout.setSpacing(6)

        title = QtWidgets.QLabel("AI 助手")
        title.setObjectName("AiFloatingTitle")
        layout.addWidget(title)
        layout.addStretch()

        expand_btn = QtWidgets.QPushButton("全屏")
        expand_btn.setObjectName("AiFloatingBtn")
        expand_btn.setFixedSize(48, 26)
        expand_btn.clicked.connect(self._on_expand)
        layout.addWidget(expand_btn)

        close_btn = QtWidgets.QPushButton("✕")
        close_btn.setObjectName("AiFloatingCloseBtn")
        close_btn.setFixedSize(26, 26)
        close_btn.clicked.connect(self._on_close)
        layout.addWidget(close_btn)

        return bar

    # ------------------------------------------------------------------
    # Geometry persistence
    # ------------------------------------------------------------------

    def _restore_geometry(self) -> None:
        settings = QtCore.QSettings("vnpy_zak", "floating_ai")
        geo = settings.value("panel_geometry")
        if geo is not None:
            self.restoreGeometry(geo)

    def _save_geometry(self) -> None:
        settings = QtCore.QSettings("vnpy_zak", "floating_ai")
        settings.setValue("panel_geometry", self.saveGeometry())

    # ------------------------------------------------------------------
    # Show / hide
    # ------------------------------------------------------------------

    def show_near(self, anchor: QtWidgets.QWidget) -> None:
        """在 anchor 窗口右下角附近弹出。"""
        if not self.isVisible():
            anchor_geo = anchor.geometry()
            x = anchor_geo.right() - self.width() - 24
            y = anchor_geo.bottom() - self.height() - 24
            self.move(anchor.mapToGlobal(QtCore.QPoint(x, y)))
        self.show()
        self.raise_()
        self.chat_panel.focus_input()

    def focus_input(self) -> None:
        self.chat_panel.focus_input()

    def set_input_text(self, text: str) -> None:
        self.chat_panel.set_input_text(text)

    def deactivate(self) -> None:
        self.chat_panel.deactivate()

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_expand(self) -> None:
        self._save_geometry()
        self.hide()
        self.expand_requested.emit()

    def _on_close(self) -> None:
        self._save_geometry()
        self.hide()
        self.panel_closed.emit()

    # ------------------------------------------------------------------
    # Title bar drag
    # ------------------------------------------------------------------

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        if event.position().y() <= TITLE_BAR_HEIGHT:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:
        if self._drag_pos is not None and event.buttons() & QtCore.Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:
        self._drag_pos = None
        super().mouseReleaseEvent(event)

    # ------------------------------------------------------------------
    # Keyboard
    # ------------------------------------------------------------------

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        if event.key() == QtCore.Qt.Key.Key_Escape:
            self._on_close()
            event.accept()
            return
        super().keyPressEvent(event)

    # ------------------------------------------------------------------
    # Close
    # ------------------------------------------------------------------

    def closeEvent(self, event) -> None:
        self._save_geometry()
        super().closeEvent(event)


# ------------------------------------------------------------------
# Stylesheet
# ------------------------------------------------------------------

_FLOATING_PANEL_STYLESHEET = PANEL_STYLESHEET + """
QWidget#FloatingAiPanel {
    background-color: #141418;
    border: 1px solid #3a3a42;
    border-radius: 10px;
}
QWidget#AiFloatingTitleBar {
    background-color: #1a1a22;
    border-top-left-radius: 10px;
    border-top-right-radius: 10px;
}
QLabel#AiFloatingTitle {
    color: #e0e0e0;
    font-size: 13px;
    font-weight: bold;
}
QPushButton#AiFloatingBtn {
    background-color: transparent;
    border: 1px solid #3a3a42;
    border-radius: 4px;
    color: #a0a0a8;
    font-size: 11px;
}
QPushButton#AiFloatingBtn:hover {
    border-color: #4a9eff;
    color: #4a9eff;
}
QPushButton#AiFloatingCloseBtn {
    background-color: transparent;
    border: 1px solid #3a3a42;
    border-radius: 4px;
    color: #a0a0a8;
    font-size: 13px;
    font-weight: bold;
}
QPushButton#AiFloatingCloseBtn:hover {
    background-color: #3a2020;
    border-color: #6a3030;
    color: #ff8a8a;
}
"""
