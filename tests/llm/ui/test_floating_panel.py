"""FloatingAiPanel 几何与拉伸单元测试。"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_llm.ui.floating.panel import PANEL_MIN_HEIGHT, PANEL_MIN_WIDTH, FloatingAiPanel


class FloatingAiPanelGeometryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def _make_panel(self, shell: QtWidgets.QWidget) -> FloatingAiPanel:
        engine = MagicMock()
        with (
            patch.object(FloatingAiPanel, "_build_ui"),
            patch("vnpy_llm.ui.floating.panel.QtCore.QTimer.singleShot"),
        ):
            return FloatingAiPanel(engine, parent=shell)

    def test_clamp_geometry_respects_parent_bounds(self) -> None:
        shell = QtWidgets.QWidget()
        shell.resize(800, 600)
        shell.show()

        panel = self._make_panel(shell)
        panel.setGeometry(500, 400, 400, 300)

        clamped = panel._clamp_geometry(panel.geometry())
        self.assertLessEqual(clamped.right(), shell.width())
        self.assertLessEqual(clamped.bottom(), shell.height())
        self.assertGreaterEqual(clamped.width(), PANEL_MIN_WIDTH)
        self.assertGreaterEqual(clamped.height(), PANEL_MIN_HEIGHT)

    def test_show_aligned_in_parent_bottom_right(self) -> None:
        parent = QtWidgets.QWidget()
        parent.resize(1000, 800)
        parent.show()

        panel = self._make_panel(parent)
        panel.chat_panel = MagicMock()
        panel.resize(360, 480)
        with (
            patch.object(panel.chat_panel, "on_floating_shown"),
            patch.object(panel.chat_panel, "focus_input"),
            patch.object(panel, "_layout_resize_handles"),
            patch.object(panel, "_update_context_bar_geometry"),
        ):
            panel.show_aligned_in_parent(parent)

        geo = panel.geometry()
        self.assertLessEqual(geo.right(), parent.width())
        self.assertLessEqual(geo.bottom(), parent.height())
        self.assertGreaterEqual(geo.x(), 0)
        self.assertGreaterEqual(geo.y(), 0)

    def test_resize_updates_height(self) -> None:
        shell = QtWidgets.QWidget()
        shell.resize(900, 700)
        shell.show()

        panel = self._make_panel(shell)
        panel.setGeometry(100, 100, 360, 480)
        start = panel.geometry()

        with patch.object(panel, "_update_context_bar_geometry"):
            panel._begin_resize(QtCore.Qt.Edge.BottomEdge, QtCore.QPoint(0, start.bottom()))
            panel._update_resize(QtCore.QPoint(0, start.bottom() + 60))
            panel._end_resize()

        self.assertEqual(panel.geometry().width(), start.width())
        self.assertGreater(panel.geometry().height(), start.height())


if __name__ == "__main__":
    unittest.main()
