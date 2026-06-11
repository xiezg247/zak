"""Qt 辅助函数单元测试。"""

from __future__ import annotations

import unittest

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_common.ui.qt_helpers import (
    clamp_point_in_parent,
    default_child_bottom_right_in_anchor,
    frame_intersects_any_screen,
    release_thread,
    restore_child_position,
    thread_is_active,
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

    def test_default_child_bottom_right_in_anchor(self) -> None:
        host = QtWidgets.QWidget()
        host.resize(1200, 800)
        sidebar = QtWidgets.QWidget(host)
        sidebar.setGeometry(0, 0, 200, 800)
        content = QtWidgets.QWidget(host)
        content.setGeometry(200, 0, 1000, 800)
        orb = QtWidgets.QWidget(host)
        orb.resize(52, 52)
        point = default_child_bottom_right_in_anchor(host, orb, content, margin=20)
        self.assertEqual(point, QtCore.QPoint(1128, 728))

    def test_frame_intersects_primary_screen(self) -> None:
        screen = QtWidgets.QApplication.primaryScreen()
        self.assertIsNotNone(screen)
        avail = screen.availableGeometry()
        self.assertTrue(frame_intersects_any_screen(avail))

    def test_release_thread_does_not_destroy_pending_start_worker(self) -> None:
        class SlowWorker(QtCore.QThread):
            def run(self) -> None:
                self.msleep(200)

        retired: list[QtCore.QThread] = []
        worker = SlowWorker()
        worker.start()
        release_thread(retired, worker, timeout_ms=0)
        self.assertIn(worker, retired)
        self.assertTrue(thread_is_active(worker) or worker.isFinished())
        worker.wait(3000)
        QtWidgets.QApplication.processEvents()
        self.assertNotIn(worker, retired)


if __name__ == "__main__":
    unittest.main()
