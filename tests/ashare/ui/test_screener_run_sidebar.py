"""选股历史侧栏单元测试。"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from vnpy.trader.ui import QtWidgets

from vnpy_ashare.ui.screener.widgets.screener_run_sidebar import (
    ScreenerRunListWidget,
    ScreenerRunSidebar,
    _radar_diff_badge,
)


class ScreenerRunListWidgetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def test_radar_diff_badge_only_for_resonance_with_new_symbols(self) -> None:
        radar = MagicMock(
            condition="雷达共振",
            source="radar",
            config={"trigger": "radar", "run_diff": {"new_count": 2}},
        )
        manual = MagicMock(
            condition="涨幅榜",
            source="quote",
            config={"trigger": "manual", "run_diff": {"new_count": 2}},
        )
        self.assertEqual(_radar_diff_badge(radar), "新增 2")
        self.assertEqual(_radar_diff_badge(manual), "")

    def test_unread_count_respects_mode_and_filter(self) -> None:
        widget = ScreenerRunListWidget(mode="auto")
        unread = MagicMock(config={"read": False, "trigger": "scheduled_intraday"})
        read = MagicMock(config={"read": True, "trigger": "scheduled_post_close"})
        strategy = MagicMock(config={"read": False, "trigger": "manual"})

        with patch("vnpy_ashare.ui.screener.widgets.screener_run_sidebar._list_runs", return_value=[unread, read, strategy]):
            with patch(
                "vnpy_ashare.ui.screener.widgets.screener_run_sidebar._is_auto_run",
                side_effect=lambda _engine, cfg: cfg.get("trigger", "").startswith("scheduled_"),
            ):
                with patch("vnpy_ashare.ui.screener.widgets.screener_run_sidebar._is_strategy_run", return_value=False):
                    with patch(
                        "vnpy_ashare.ui.screener.widgets.screener_run_sidebar._is_run_unread",
                        side_effect=lambda _engine, cfg: not cfg.get("read", True),
                    ):
                        self.assertEqual(widget.unread_count(), 1)

                        widget._filter = "intraday"
                        self.assertEqual(widget.unread_count(), 1)

                        widget._filter = "post_close"
                        self.assertEqual(widget.unread_count(), 0)


class ScreenerRunSidebarTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def test_sidebar_init_does_not_crash_during_list_refresh(self) -> None:
        with patch("vnpy_ashare.ui.screener.widgets.screener_run_sidebar._list_runs", return_value=[]):
            sidebar = ScreenerRunSidebar(mode="auto")
            self.assertIsNotNone(sidebar._list)


if __name__ == "__main__":
    unittest.main()
