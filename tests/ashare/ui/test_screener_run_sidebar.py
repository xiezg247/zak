"""选股历史侧栏单元测试。"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from vnpy.trader.ui import QtWidgets

from vnpy_ashare.ui.screener_run_sidebar import ScreenerRunListWidget


class ScreenerRunListWidgetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def test_unread_count_respects_mode_and_filter(self) -> None:
        widget = ScreenerRunListWidget(mode="auto")
        unread = MagicMock(config={"read": False, "trigger": "scheduled_intraday"})
        read = MagicMock(config={"read": True, "trigger": "scheduled_post_close"})
        strategy = MagicMock(config={"read": False, "trigger": "manual"})

        with patch("vnpy_ashare.ui.screener_run_sidebar.list_runs", return_value=[unread, read, strategy]):
            with patch("vnpy_ashare.ui.screener_run_sidebar.is_auto_run", side_effect=lambda cfg: cfg.get("trigger", "").startswith("scheduled_")):
                with patch("vnpy_ashare.ui.screener_run_sidebar.is_strategy_run", return_value=False):
                    with patch("vnpy_ashare.ui.screener_run_sidebar.is_run_unread", side_effect=lambda cfg: not cfg.get("read", True)):
                        self.assertEqual(widget.unread_count(), 1)

                        widget._filter = "intraday"
                        self.assertEqual(widget.unread_count(), 1)

                        widget._filter = "post_close"
                        self.assertEqual(widget.unread_count(), 0)


if __name__ == "__main__":
    unittest.main()
