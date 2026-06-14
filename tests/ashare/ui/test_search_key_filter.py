"""行情页搜索框按键过滤（IME 兼容）。"""

from __future__ import annotations

import unittest
from unittest.mock import Mock

from vnpy.trader.ui import QtCore, QtGui, QtWidgets

import tests._bootstrap  # noqa: F401
from vnpy_ashare.ui.quotes.page.shell import _SearchKeyFilter


class SearchKeyFilterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def test_enter_not_swallowed_for_ime(self) -> None:
        page = Mock()
        page.search_edit = QtWidgets.QLineEdit()
        page._search_timer = Mock()
        page.apply_filter = Mock()
        filt = _SearchKeyFilter(page)

        event = QtGui.QKeyEvent(
            QtCore.QEvent.Type.KeyPress,
            QtCore.Qt.Key.Key_Return,
            QtCore.Qt.KeyboardModifier.NoModifier,
        )
        handled = filt.eventFilter(page.search_edit, event)
        self.assertFalse(handled)
        page.apply_filter.assert_not_called()

    def test_escape_clears_and_filters(self) -> None:
        page = Mock()
        page.search_edit = QtWidgets.QLineEdit()
        page.search_edit.setText("600519")
        page._search_timer = Mock()
        page.apply_filter = Mock()
        filt = _SearchKeyFilter(page)

        event = QtGui.QKeyEvent(
            QtCore.QEvent.Type.KeyPress,
            QtCore.Qt.Key.Key_Escape,
            QtCore.Qt.KeyboardModifier.NoModifier,
        )
        handled = filt.eventFilter(page.search_edit, event)
        self.assertTrue(handled)
        self.assertEqual(page.search_edit.text(), "")
        page._search_timer.stop.assert_called_once()
        page.apply_filter.assert_called_once()


if __name__ == "__main__":
    unittest.main()
