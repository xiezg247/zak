"""ScreenerSelectionController / ScreenerSchemeController 单元测试。"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from vnpy_ashare.ui.screener.pages.screener_scheme_controller import ScreenerSchemeController
from vnpy_ashare.ui.screener.pages.screener_selection_controller import ScreenerSelectionController


class ScreenerSelectionControllerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.page = MagicMock()
        self.page._watchlist_service = MagicMock()
        self.page._watchlist_service.max_items = 50
        self.page._task_guard = MagicMock()
        self.page._task_guard.active = False
        self.page._task_guard.cancelled = False
        self.page._download_worker = None
        self.page._active = True
        self.page._task_lock_widgets.return_value = []
        self.page._last_run_config = {}
        self.page._batch_backtest_flow = MagicMock()
        self.page._batch_backtest_flow.is_running.return_value = False
        self.controller = ScreenerSelectionController(self.page)

    @patch("vnpy_ashare.ui.screener.pages.screener_selection_controller.iter_checked_table_rows")
    @patch("vnpy_ashare.ui.screener.pages.screener_selection_controller.confirm_recession_batch_watchlist")
    def test_add_to_watchlist_success(self, confirm: MagicMock, iter_rows: MagicMock) -> None:
        confirm.return_value = True
        iter_rows.return_value = [{"vt_symbol": "600519.SH", "name": "茅台"}]
        self.page._watchlist_service.add.return_value = True

        self.controller.add_to_watchlist()

        self.page._watchlist_service.add.assert_called_once()
        self.page._toast.success.assert_called_once()

    @patch("vnpy_ashare.ui.screener.pages.screener_selection_controller.iter_checked_table_rows")
    def test_download_selected_bars_skips_when_empty(self, iter_rows: MagicMock) -> None:
        iter_rows.return_value = []

        self.controller.download_selected_bars()

        self.page._task_guard.begin.assert_not_called()

    @patch("vnpy_ashare.ui.screener.pages.screener_selection_controller.ScreenerBatchDownloadWorker")
    @patch("vnpy_ashare.ui.screener.pages.screener_selection_controller.iter_checked_table_rows")
    def test_download_selected_bars_starts_worker(self, iter_rows: MagicMock, worker_cls: MagicMock) -> None:
        iter_rows.return_value = [{"vt_symbol": "600519.SH"}]
        worker = MagicMock()
        worker_cls.return_value = worker

        self.controller.download_selected_bars()

        worker_cls.assert_called_once()
        worker.start.assert_called_once()
        self.assertIs(self.page._download_worker, worker)

    @patch("vnpy_ashare.ui.screener.pages.screener_selection_controller.get_backtest_service")
    @patch("vnpy_ashare.ui.screener.pages.screener_selection_controller.iter_checked_table_rows")
    def test_run_batch_backtest_uses_default_source(self, iter_rows: MagicMock, get_service: MagicMock) -> None:
        iter_rows.return_value = [{"vt_symbol": "600519.SH"}]
        get_service.return_value = MagicMock(list_strategies=lambda: [])

        self.controller.run_batch_backtest(
            source_page="选股",
            default_batch_source="batch_screener",
        )

        flow = self.page._batch_backtest_flow
        flow.start.assert_called_once()
        self.assertEqual(flow.start.call_args.kwargs["batch_source"], "batch_screener")


class ScreenerSchemeControllerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.page = MagicMock()
        self.page.preset_combo.currentText.return_value = "涨幅榜"
        self.page._current_scheme_id.return_value = None
        self.page.industry_edit.text.return_value = ""
        self.controller = ScreenerSchemeController(self.page)

    def test_delete_scheme_requires_custom_scheme(self) -> None:
        self.page._current_scheme_id.return_value = None

        self.controller.delete_scheme()

        self.page._toast.info.assert_called_once()

    @patch("vnpy_ashare.ui.screener.pages.screener_scheme_controller.confirm_action")
    def test_delete_scheme_calls_service(self, confirm: MagicMock) -> None:
        confirm.return_value = True
        self.page._current_scheme_id.return_value = "scheme-1"
        service = MagicMock()
        self.page._screening_service.return_value = service

        self.controller.delete_scheme()

        service.delete_scheme.assert_called_once_with("scheme-1")
        self.page._reload_preset_combo.assert_called_once()


if __name__ == "__main__":
    unittest.main()
