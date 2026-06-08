"""Qt 辅助函数单元测试。"""

from __future__ import annotations

import unittest

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.ui.qt_helpers import (
    clamp_point_in_parent,
    frame_intersects_any_screen,
    restore_child_position,
)


class QtHelpersTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def test_clamp_point_in_parent(self) -> None:
        parent = QtWidgets.QWidget()
        parent.resize(400, 300)
        child = QtWidgets.QWidget(parent)
        child.resize(80, 80)
        point = clamp_point_in_parent(parent, child, QtCore.QPoint(999, -50))
        self.assertEqual(point.x(), 320)
        self.assertEqual(point.y(), 0)

    def test_restore_child_position_uses_default_when_invalid(self) -> None:
        parent = QtWidgets.QWidget()
        parent.resize(500, 400)
        child = QtWidgets.QWidget(parent)
        child.resize(52, 52)
        restore_child_position(parent, child, None, default_x=300, default_y=200)
        self.assertEqual(child.pos(), QtCore.QPoint(300, 200))

    def test_frame_intersects_primary_screen(self) -> None:
        screen = QtWidgets.QApplication.primaryScreen()
        self.assertIsNotNone(screen)
        avail = screen.availableGeometry()
        self.assertTrue(frame_intersects_any_screen(avail))


if __name__ == "__main__":
    unittest.main()
