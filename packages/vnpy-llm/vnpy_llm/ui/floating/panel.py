"""浮动 AI 悬浮球与精简对话面板。"""

from __future__ import annotations

import math
from typing import cast

from vnpy.trader.ui import QtCore, QtGui, QtWidgets

from vnpy_common.ai.protocol import AiContextData
from vnpy_common.paths import QSETTINGS_ORG
from vnpy_common.ui.feedback import PageToastHost
from vnpy_common.ui.qt_helpers import (
    clamp_point_in_parent,
    ensure_geometry_on_screen,
    frame_intersects_any_screen,
    restore_child_position,
)
from vnpy_common.ui.theme import theme_manager
from vnpy_common.ui.theme.orb_palette import OrbPalette, orb_palette
from vnpy_common.ui.theme.tokens import ThemeTokens
from vnpy_llm.app.engine import LlmEngine
from vnpy_llm.ui.floating.context_labels import orb_tooltip_text
from vnpy_llm.ui.panel.chat import AiChatPanel
from vnpy_llm.ui.themed_styles import bind_ai_floating_style

ORB_SIZE = 52
ORB_MARGIN = 20
PANEL_WIDTH = 360
PANEL_HEIGHT = 480
PANEL_MIN_WIDTH = 300
PANEL_MIN_HEIGHT = 380
TITLE_BAR_HEIGHT = 32
RESIZE_MARGIN = 10

ResizeEdges = int

BTN_MARGIN = ORB_MARGIN


class _PanelResizeHandle(QtWidgets.QWidget):
    """面板边缘拖拽拉伸句柄（透明覆盖层）。"""

    def __init__(self, panel: FloatingAiPanel, edges: ResizeEdges) -> None:
        super().__init__(panel)
        self._panel = panel
        self._edges = edges
        self.setCursor(panel._cursor_for_edges(edges))

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self._panel._begin_resize(self._edges, event.globalPosition().toPoint())
            event.accept()
            return
        super().mousePressEvent(event)


class FloatingAiOrb(QtWidgets.QWidget):
    """可拖拽的 AI 悬浮球。"""

    clicked = QtCore.Signal()
    fullscreen_requested = QtCore.Signal()
    history_requested = QtCore.Signal()
    new_session_requested = QtCore.Signal()
    tools_requested = QtCore.Signal()
    hide_requested = QtCore.Signal()
    quick_action_requested = QtCore.Signal(str)

    def __init__(
        self,
        parent: QtWidgets.QWidget | None = None,
        *,
        position_key: str = "orb_position",
    ) -> None:
        super().__init__(parent)
        self._position_key = position_key
        self.setObjectName("FloatingAiOrb")
        self.setFixedSize(ORB_SIZE, ORB_SIZE)
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.setToolTip("AI 助手 · 左键对话 · 右键菜单 · Ctrl+L 显示/隐藏")
        self.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

        self._drag_offset: QtCore.QPoint | None = None
        self._press_global: QtCore.QPoint | None = None
        self._dragging = False
        self._hovered = False
        self._badge_text = ""
        self._context_actions: list = []
        self._attention_strength = 0.0
        self._attention_timer = QtCore.QTimer(self)
        self._attention_timer.setInterval(80)
        self._attention_timer.timeout.connect(self._on_attention_tick)
        self._palette: OrbPalette = orb_palette(theme_manager().tokens())
        theme_manager().register_callback(self._on_theme_changed)

    def _on_theme_changed(self, tokens: ThemeTokens) -> None:
        self._palette = orb_palette(tokens)
        self.update()

    def play_attention_pulse(self) -> None:
        """选股完成等场景：短暂高亮，不展开面板。"""
        self._attention_strength = 1.0
        self._attention_timer.start()

    def _on_attention_tick(self) -> None:
        self._attention_strength = max(0.0, self._attention_strength - 0.1)
        self.update()
        if self._attention_strength <= 0:
            self._attention_timer.stop()

    def apply_context(self, data: AiContextData) -> None:
        self._badge_text = (data.badge or "")[:8]
        self._context_actions = list(data.actions)
        self.setToolTip(orb_tooltip_text(data))
        self.update()

    @staticmethod
    def _draw_sparkle(
        painter: QtGui.QPainter,
        cx: float,
        cy: float,
        size: float,
        color: QtGui.QColor,
    ) -> None:
        path = QtGui.QPainterPath()
        for index in range(8):
            angle = index * math.pi / 4 - math.pi / 2
            radius = size if index % 2 == 0 else size * 0.28
            point = QtCore.QPointF(cx + radius * math.cos(angle), cy + radius * math.sin(angle))
            if index == 0:
                path.moveTo(point)
            else:
                path.lineTo(point)
        path.closeSubpath()
        painter.setPen(QtCore.Qt.PenStyle.NoPen)
        painter.setBrush(color)
        painter.drawPath(path)

    def _paint_orb_icon(self, painter: QtGui.QPainter) -> None:
        palette = self._palette
        center = QtCore.QPointF(ORB_SIZE / 2, ORB_SIZE / 2 + 0.5)
        radius = 21.0

        attention = self._attention_strength
        glow_alpha = palette.glow_center.alpha() + int(90 * attention)
        if self._hovered:
            glow_alpha += 22
        glow = QtGui.QRadialGradient(center + QtCore.QPointF(0, 3), radius + 6 + attention * 6)
        glow_center = QtGui.QColor(palette.glow_center)
        glow_center.setAlpha(min(255, glow_alpha))
        glow.setColorAt(0.0, glow_center)
        glow.setColorAt(1.0, palette.glow_edge)
        painter.setPen(QtCore.Qt.PenStyle.NoPen)
        painter.setBrush(glow)
        painter.drawEllipse(
            center + QtCore.QPointF(0, 4),
            radius + 4 + attention * 4,
            radius + 3 + attention * 3,
        )
        if attention > 0.05:
            ring = QtGui.QPen(palette.attention_ring, 2.0)
            ring_color = QtGui.QColor(ring.color())
            ring_color.setAlpha(int(180 * attention))
            ring.setColor(ring_color)
            painter.setPen(ring)
            painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
            painter.drawEllipse(center, radius + 2 + attention * 3, radius + 2 + attention * 3)
            painter.setPen(QtCore.Qt.PenStyle.NoPen)

        stops = palette.hover_gradient if self._hovered else palette.idle_gradient
        orb_gradient = QtGui.QRadialGradient(center + QtCore.QPointF(-7, -8), radius * 1.55)
        for pos, color in stops:
            orb_gradient.setColorAt(pos, color)

        painter.setBrush(orb_gradient)
        painter.drawEllipse(center, radius, radius)

        painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
        painter.setPen(QtGui.QPen(palette.rim, 1.0))
        painter.drawEllipse(center, radius - 0.6, radius - 0.6)

        specular = QtGui.QRadialGradient(center + QtCore.QPointF(-8, -10), 13)
        for pos, color in palette.specular:
            specular.setColorAt(pos, color)
        painter.setPen(QtCore.Qt.PenStyle.NoPen)
        painter.setBrush(specular)
        painter.drawEllipse(center + QtCore.QPointF(-7, -9), 11.5, 8.0)

        self._draw_sparkle(painter, center.x(), center.y() - 1.5, 8.5, palette.sparkle_primary)
        self._draw_sparkle(painter, center.x() + 10.5, center.y() - 9.0, 4.2, palette.sparkle_secondary)
        self._draw_sparkle(painter, center.x() - 10.8, center.y() + 8.2, 3.4, palette.sparkle_tertiary)

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform)
        self._paint_orb_icon(painter)
        if self._badge_text:
            self._paint_badge(painter)
        painter.end()

    def _paint_badge(self, painter: QtGui.QPainter) -> None:
        palette = self._palette
        font = painter.font()
        font.setPixelSize(9)
        font.setBold(True)
        painter.setFont(font)
        metrics = QtGui.QFontMetrics(font)
        text = self._badge_text
        width = min(metrics.horizontalAdvance(text) + 8, ORB_SIZE - 4)
        height = 14
        rect = QtCore.QRectF(ORB_SIZE - width - 2, 2, width, height)
        badge_bg = palette.badge_bg_attention if self._attention_strength > 0.05 else palette.badge_bg
        painter.setPen(QtCore.Qt.PenStyle.NoPen)
        painter.setBrush(badge_bg)
        painter.drawRoundedRect(rect, 4, 4)
        badge_text = palette.badge_text_attention if self._attention_strength > 0.05 else palette.badge_text
        painter.setPen(badge_text)
        painter.drawText(rect, QtCore.Qt.AlignmentFlag.AlignCenter, text)

    def enterEvent(self, event: QtCore.QEvent) -> None:
        self._hovered = True
        self.update()
        super().enterEvent(event)  # type: ignore[arg-type]

    def leaveEvent(self, event: QtCore.QEvent) -> None:
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self._press_global = event.globalPosition().toPoint()
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self._dragging = False
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:
        if self._drag_offset is not None and event.buttons() & QtCore.Qt.MouseButton.LeftButton:
            if self._press_global is not None:
                delta = event.globalPosition().toPoint() - self._press_global
                if delta.manhattanLength() > 4:
                    self._dragging = True
            self.move(event.globalPosition().toPoint() - self._drag_offset)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            if not self._dragging:
                self.clicked.emit()
            else:
                self._save_position()
            self._drag_offset = None
            self._press_global = None
            self._dragging = False
        super().mouseReleaseEvent(event)

    def _show_context_menu(self, pos: QtCore.QPoint) -> None:
        menu = QtWidgets.QMenu(self)
        menu.setObjectName("FloatingAiOrbMenu")
        menu.addAction("打开对话", lambda: self.clicked.emit())
        if self._context_actions:
            menu.addSeparator()
            for action in self._context_actions[:5]:
                prompt = action.prompt

                def _emit_quick_action(*, _prompt: str = prompt) -> None:
                    self.quick_action_requested.emit(_prompt)

                menu.addAction(action.label, _emit_quick_action)
        menu.addSeparator()
        menu.addAction("全屏模式", self.fullscreen_requested.emit)
        menu.addSeparator()
        menu.addAction("新会话", self.new_session_requested.emit)
        menu.addAction("历史会话…", self.history_requested.emit)
        menu.addAction("AI 工具能力…", self.tools_requested.emit)
        menu.addSeparator()
        menu.addAction("隐藏悬浮球", self.hide_requested.emit)
        menu.exec(self.mapToGlobal(pos))

    def restore_position(
        self,
        shell: QtWidgets.QWidget | None = None,
        *,
        default_x: int | None = None,
        default_y: int | None = None,
    ) -> None:
        if shell is None:
            shell = self.parentWidget()
        if shell is None:
            return
        if default_x is None:
            default_x = shell.width() - self.width() - ORB_MARGIN
        if default_y is None:
            default_y = shell.height() - self.height() - ORB_MARGIN
        settings = QtCore.QSettings(QSETTINGS_ORG, "floating_ai")
        pos = settings.value(self._position_key)
        restore_child_position(
            shell,
            self,
            pos,
            default_x=default_x,
            default_y=default_y,
        )

    def _save_position(self) -> None:
        settings = QtCore.QSettings(QSETTINGS_ORG, "floating_ai")
        settings.setValue(self._position_key, self.pos())

    def clamp_to_parent(self, shell: QtWidgets.QWidget | None = None) -> None:
        if shell is None:
            shell = self.parentWidget()
        if shell is None:
            return
        self.move(clamp_point_in_parent(shell, self, self.pos()))


class FloatingAiPanel(QtWidgets.QWidget):
    """精简浮动对话面板（无边框工具窗口）。"""

    expand_requested = QtCore.Signal()
    panel_minimized = QtCore.Signal()
    new_session_requested = QtCore.Signal()
    history_requested = QtCore.Signal()
    quick_action_triggered = QtCore.Signal(object)

    def __init__(
        self,
        engine: LlmEngine,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("FloatingAiPanel")
        self.setMinimumSize(PANEL_MIN_WIDTH, PANEL_MIN_HEIGHT)
        self.resize(PANEL_WIDTH, PANEL_HEIGHT)

        self._drag_pos: QtCore.QPoint | None = None
        self._resizing = False
        self._resize_edges: ResizeEdges = 0
        self._resize_start_geom: QtCore.QRect | None = None
        self._resize_start_global: QtCore.QPoint | None = None
        self._resize_right = _PanelResizeHandle(
            self,
            cast(ResizeEdges, QtCore.Qt.Edge.RightEdge),
        )
        self._resize_bottom = _PanelResizeHandle(
            self,
            cast(ResizeEdges, QtCore.Qt.Edge.BottomEdge),
        )
        self._resize_corner = _PanelResizeHandle(
            self,
            cast(ResizeEdges, QtCore.Qt.Edge.RightEdge | QtCore.Qt.Edge.BottomEdge),
        )

        self._build_ui(engine)
        QtCore.QTimer.singleShot(0, self._restore_geometry)

    def _build_ui(self, engine: LlmEngine) -> None:
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        title_bar = self._build_title_bar()
        root.addWidget(title_bar)

        self.context_bar = QtWidgets.QWidget()
        self.context_bar.setObjectName("AiFloatingContextBar")
        self.context_bar.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)
        context_layout = QtWidgets.QHBoxLayout(self.context_bar)
        context_layout.setContentsMargins(10, 8, 10, 8)
        context_layout.setSpacing(0)
        self.context_chip = QtWidgets.QLabel("AI 助手")
        self.context_chip.setObjectName("AiFloatingContextChip")
        self.context_chip.setWordWrap(True)
        self.context_chip.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Preferred,
        )
        context_layout.addWidget(self.context_chip)
        self.context_bar.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Preferred,
            QtWidgets.QSizePolicy.Policy.Fixed,
        )
        root.addWidget(self.context_bar, 0)

        self.chat_panel = AiChatPanel(engine, floating=True, parent=self)
        self.chat_panel.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Preferred,
            QtWidgets.QSizePolicy.Policy.Expanding,
        )
        self.chat_panel.expand_requested.connect(self._on_expand)
        root.addWidget(self.chat_panel, 1)

        self._toast = PageToastHost(self)
        root.addWidget(self._toast)

        bind_ai_floating_style(self)
        self._layout_resize_handles()
        self._update_context_bar_geometry()

    def _build_title_bar(self) -> QtWidgets.QWidget:
        bar = QtWidgets.QWidget()
        bar.setObjectName("AiFloatingTitleBar")
        bar.setFixedHeight(TITLE_BAR_HEIGHT)

        layout = QtWidgets.QHBoxLayout(bar)
        layout.setContentsMargins(10, 0, 6, 0)
        layout.setSpacing(4)

        grip = QtWidgets.QLabel("⠿")
        grip.setObjectName("AiFloatingGrip")
        layout.addWidget(grip)

        title = QtWidgets.QLabel("AI")
        title.setObjectName("AiFloatingTitle")
        layout.addWidget(title)
        layout.addStretch()

        new_btn = QtWidgets.QToolButton()
        new_btn.setObjectName("AiFloatingIconBtn")
        new_btn.setText("＋")
        new_btn.setToolTip("新会话")
        new_btn.setFixedSize(24, 24)
        new_btn.clicked.connect(self.new_session_requested.emit)
        layout.addWidget(new_btn)

        history_btn = QtWidgets.QToolButton()
        history_btn.setObjectName("AiFloatingIconBtn")
        history_btn.setText("⌚")
        history_btn.setToolTip("历史会话")
        history_btn.setFixedSize(24, 24)
        history_btn.clicked.connect(self.history_requested.emit)
        layout.addWidget(history_btn)

        expand_btn = QtWidgets.QToolButton()
        expand_btn.setObjectName("AiFloatingIconBtn")
        expand_btn.setText("⛶")
        expand_btn.setToolTip("全屏")
        expand_btn.setFixedSize(24, 24)
        expand_btn.clicked.connect(self._on_expand)
        layout.addWidget(expand_btn)

        minimize_btn = QtWidgets.QToolButton()
        minimize_btn.setObjectName("AiFloatingIconBtn")
        minimize_btn.setText("—")
        minimize_btn.setToolTip("收起")
        minimize_btn.setFixedSize(24, 24)
        minimize_btn.clicked.connect(self._on_minimize)
        layout.addWidget(minimize_btn)

        return bar

    def _restore_geometry(self) -> None:
        settings = QtCore.QSettings(QSETTINGS_ORG, "floating_ai")
        geometry = settings.value("panel_geometry")
        if isinstance(geometry, QtCore.QByteArray) and not geometry.isEmpty():
            self.restoreGeometry(geometry)
            if not frame_intersects_any_screen(self.frameGeometry()):
                ensure_geometry_on_screen(self)
        else:
            ensure_geometry_on_screen(self)
        # 仅恢复位置/尺寸，不沿用上次可见状态（默认收起面板）
        self.hide()

    def _save_geometry(self) -> None:
        settings = QtCore.QSettings(QSETTINGS_ORG, "floating_ai")
        settings.setValue("panel_geometry", self.saveGeometry())

    def show_aligned_in_parent(self, parent: QtWidgets.QWidget | None = None) -> None:
        """在指定父控件右下角弹出面板（用于模态窗等 overlay 场景）。"""
        anchor = parent or self.parentWidget()
        if anchor is None:
            self.show()
            self.raise_()
            self.chat_panel.on_floating_shown()
            self.chat_panel.focus_input()
            return
        margin = ORB_MARGIN
        width = min(self.width(), max(self.minimumWidth(), anchor.width() - 2 * margin))
        height = min(self.height(), max(self.minimumHeight(), anchor.height() - 2 * margin))
        x = max(0, anchor.width() - width - margin)
        y = max(0, anchor.height() - height - margin)
        self.setGeometry(self._clamp_geometry(QtCore.QRect(x, y, width, height)))
        self.show()
        self.raise_()
        self._layout_resize_handles()
        self._update_context_bar_geometry()
        self.chat_panel.on_floating_shown()
        self.chat_panel.focus_input()

    def show_near_orb(self, orb: FloatingAiOrb) -> None:
        """在悬浮球附近弹出面板。"""
        shell = self.parentWidget() or orb.parentWidget()
        if shell is not None:
            orb_pos = orb.pos()
            x = orb_pos.x() - self.width() + orb.width()
            y = orb_pos.y() - self.height() - 12
            if y < 0:
                y = orb_pos.y() + orb.height() + 12
            self.move(clamp_point_in_parent(shell, self, QtCore.QPoint(x, y)))
        else:
            orb_global = orb.mapToGlobal(QtCore.QPoint(0, 0))
            x = orb_global.x() - self.width() + orb.width()
            y = orb_global.y() - self.height() - 12
            if y < 0:
                y = orb_global.y() + orb.height() + 12
            self.move(x, y)
            ensure_geometry_on_screen(self)
        self.show()
        self.raise_()
        self._layout_resize_handles()
        self._update_context_bar_geometry()
        self.chat_panel.on_floating_shown()
        self.chat_panel.focus_input()

    def _update_context_bar_geometry(self) -> None:
        content_width = max(self.width() - 20, 200)
        chip_height = self.context_chip.heightForWidth(content_width)
        self.context_bar.setFixedHeight(max(40, chip_height + 16))

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:
        super().resizeEvent(event)
        self._layout_resize_handles()
        self._update_context_bar_geometry()

    def clamp_geometry_to_parent(self) -> None:
        """父窗口尺寸变化时，将面板限制在可见区域内。"""
        clamped = self._clamp_geometry(self.geometry())
        if clamped != self.geometry():
            self.setGeometry(clamped)
            self._update_context_bar_geometry()

    @staticmethod
    def _cursor_for_edges(edges: ResizeEdges) -> QtCore.Qt.CursorShape:
        right = cast(ResizeEdges, QtCore.Qt.Edge.RightEdge)
        bottom = cast(ResizeEdges, QtCore.Qt.Edge.BottomEdge)
        if edges & right and edges & bottom:
            return QtCore.Qt.CursorShape.SizeFDiagCursor
        if edges & right:
            return QtCore.Qt.CursorShape.SizeHorCursor
        if edges & bottom:
            return QtCore.Qt.CursorShape.SizeVerCursor
        return QtCore.Qt.CursorShape.ArrowCursor

    def _layout_resize_handles(self) -> None:
        margin = RESIZE_MARGIN
        top = TITLE_BAR_HEIGHT
        width = self.width()
        height = self.height()
        body_height = max(0, height - top)
        self._resize_right.setGeometry(width - margin, top, margin, body_height)
        self._resize_bottom.setGeometry(0, height - margin, max(0, width - margin), margin)
        self._resize_corner.setGeometry(width - margin, height - margin, margin, margin)
        for handle in (self._resize_right, self._resize_bottom, self._resize_corner):
            handle.raise_()

    def _clamp_geometry(self, geo: QtCore.QRect) -> QtCore.QRect:
        width = max(self.minimumWidth(), geo.width())
        height = max(self.minimumHeight(), geo.height())
        x = geo.x()
        y = geo.y()
        parent = self.parentWidget()
        if parent is not None:
            width = min(width, max(self.minimumWidth(), parent.width() - x))
            height = min(height, max(self.minimumHeight(), parent.height() - y))
            x = min(max(0, x), max(0, parent.width() - width))
            y = min(max(0, y), max(0, parent.height() - height))
        return QtCore.QRect(x, y, width, height)

    def _begin_resize(self, edges: ResizeEdges, global_pos: QtCore.QPoint) -> None:
        self._resizing = True
        self._resize_edges = edges
        self._resize_start_geom = self.geometry()
        self._resize_start_global = global_pos
        self.grabMouse()

    def _update_resize(self, global_pos: QtCore.QPoint) -> None:
        if not self._resizing or self._resize_start_geom is None or self._resize_start_global is None:
            return
        delta = global_pos - self._resize_start_global
        geo = QtCore.QRect(self._resize_start_geom)
        right = cast(ResizeEdges, QtCore.Qt.Edge.RightEdge)
        bottom = cast(ResizeEdges, QtCore.Qt.Edge.BottomEdge)
        if self._resize_edges & right:
            geo.setWidth(self._resize_start_geom.width() + delta.x())
        if self._resize_edges & bottom:
            geo.setHeight(self._resize_start_geom.height() + delta.y())
        self.setGeometry(self._clamp_geometry(geo))
        self._update_context_bar_geometry()

    def _end_resize(self) -> None:
        if not self._resizing:
            return
        self._resizing = False
        self._resize_edges = 0
        self._resize_start_geom = None
        self._resize_start_global = None
        self.releaseMouse()
        self._save_geometry()

    def focus_input(self) -> None:
        self.chat_panel.focus_input()

    def set_input_text(self, text: str) -> None:
        self.chat_panel.set_input_text(text)

    def deactivate(self) -> None:
        self.hide()
        self.chat_panel.deactivate(final=True)

    def apply_context(self, data: AiContextData) -> None:
        chip = data.chip_text or "AI 助手"
        self.context_chip.setText(chip)
        detail = data.to_text()
        self.context_chip.setToolTip(detail if detail else chip)
        self._update_context_bar_geometry()
        self.chat_panel.set_quick_actions(data.actions)

    def submit_prompt(self, text: str, *, auto_send: bool = False, action_id: str = "") -> None:
        self.chat_panel.submit_prompt(text, auto_send=auto_send, action_id=action_id)

    def _on_expand(self) -> None:
        self._save_geometry()
        self.hide()
        self.expand_requested.emit()

    def _on_minimize(self) -> None:
        self._save_geometry()
        self.hide()
        self.panel_minimized.emit()

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        if event.position().y() <= TITLE_BAR_HEIGHT:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:
        if self._resizing:
            self._update_resize(event.globalPosition().toPoint())
            event.accept()
            return
        if self._drag_pos is not None and event.buttons() & QtCore.Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:
        if self._resizing:
            self._end_resize()
            event.accept()
            return
        self._drag_pos = None
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        if event.key() == QtCore.Qt.Key.Key_Escape:
            self._on_minimize()
            event.accept()
            return
        super().keyPressEvent(event)

    def closeEvent(self, event) -> None:
        self._save_geometry()
        super().closeEvent(event)
