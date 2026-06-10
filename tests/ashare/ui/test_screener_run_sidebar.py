"""选股历史侧栏单元测试。"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from vnpy.trader.ui import QtWidgets

from vnpy_ashare.ui.screener.screener_run_sidebar import ScreenerRunListWidget, ScreenerRunSidebar


def _auto_record(run_id: str, *, trigger: str = "scheduled_intraday", read: bool = True):
    return MagicMock(
        id=run_id,
        condition=f"条件-{run_id}",
        source="test",
        row_count=3,
        total_scanned=100,
        created_at="2026-06-09 20:17:00",
        config={"trigger": trigger, "read": read},
    )


def _strategy_record(run_id: str):
    return MagicMock(
        id=run_id,
        condition=f"条件-{run_id}",
        source="test",
        row_count=5,
        total_scanned=200,
        created_at="2026-06-09 20:17:00",
        config={"trigger": "manual", "read": True},
    )


class ScreenerRunListWidgetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def test_unread_count_respects_mode_and_filter(self) -> None:
        widget = ScreenerRunListWidget(mode="auto")
        unread = MagicMock(config={"read": False, "trigger": "scheduled_intraday"})
        read = MagicMock(config={"read": True, "trigger": "scheduled_post_close"})
        strategy = MagicMock(config={"read": False, "trigger": "manual"})

        with patch("vnpy_ashare.ui.screener.screener_run_sidebar._list_runs", return_value=[unread, read, strategy]):
            with patch(
                "vnpy_ashare.ui.screener.screener_run_sidebar._is_auto_run",
                side_effect=lambda _engine, cfg: cfg.get("trigger", "").startswith("scheduled_"),
            ):
                with patch("vnpy_ashare.ui.screener.screener_run_sidebar._is_strategy_run", return_value=False):
                    with patch(
                        "vnpy_ashare.ui.screener.screener_run_sidebar._is_run_unread",
                        side_effect=lambda _engine, cfg: not cfg.get("read", True),
                    ):
                        self.assertEqual(widget.unread_count(), 1)

                        widget._filter = "intraday"
                        self.assertEqual(widget.unread_count(), 1)

                        widget._filter = "post_close"
                        self.assertEqual(widget.unread_count(), 0)

    def test_auto_mode_supports_multi_select_delete(self) -> None:
        widget = ScreenerRunListWidget(mode="auto")
        records = [_auto_record("run-a"), _auto_record("run-b")]
        deleted: list[str] = []

        with patch("vnpy_ashare.ui.screener.screener_run_sidebar._list_runs", return_value=records):
            with patch("vnpy_ashare.ui.screener.screener_run_sidebar._is_auto_run", return_value=True):
                with patch("vnpy_ashare.ui.screener.screener_run_sidebar._is_run_unread", return_value=False):
                    with patch(
                        "vnpy_ashare.ui.screener.screener_run_sidebar._delete_run",
                        side_effect=lambda _engine, run_id: deleted.append(run_id),
                    ):
                        widget.refresh()
                        widget._set_multi_select_mode(True, preselect_run_id="run-a")
                        widget._multi_checked_ids.add("run-b")
                        with patch.object(QtWidgets.QMessageBox, "question", return_value=QtWidgets.QMessageBox.StandardButton.Yes):
                            widget._on_delete_selected()
                        self.assertEqual(set(deleted), {"run-a", "run-b"})
                        self.assertFalse(widget._multi_select_mode)

    def test_strategy_mode_supports_multi_select_delete(self) -> None:
        widget = ScreenerRunListWidget(mode="strategy")
        records = [_strategy_record("run-a"), _strategy_record("run-b")]
        deleted: list[str] = []

        with patch("vnpy_ashare.ui.screener.screener_run_sidebar._list_runs", return_value=records):
            with patch("vnpy_ashare.ui.screener.screener_run_sidebar._is_strategy_run", return_value=True):
                with patch("vnpy_ashare.ui.screener.screener_run_sidebar._is_run_unread", return_value=False):
                    with patch(
                        "vnpy_ashare.ui.screener.screener_run_sidebar._delete_run",
                        side_effect=lambda _engine, run_id: deleted.append(run_id),
                    ):
                        widget.refresh()
                        widget._set_multi_select_mode(True, preselect_run_id="run-a")
                        widget._multi_checked_ids.add("run-b")
                        with patch.object(QtWidgets.QMessageBox, "question", return_value=QtWidgets.QMessageBox.StandardButton.Yes):
                            widget._on_delete_selected()
                        self.assertEqual(set(deleted), {"run-a", "run-b"})
                        self.assertFalse(widget._multi_select_mode)


class ScreenerRunSidebarTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def test_sidebar_init_does_not_crash_during_list_refresh(self) -> None:
        with patch("vnpy_ashare.ui.screener.screener_run_sidebar._list_runs", return_value=[]):
            sidebar = ScreenerRunSidebar(mode="auto")
            self.assertIsNotNone(sidebar._list)


if __name__ == "__main__":
    unittest.main()
