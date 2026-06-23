"""页面 session 生命周期单元测试。"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from vnpy_ashare.ui.quotes.page.session_lifecycle import activate_quotes_page, deactivate_quotes_page
from vnpy_ashare.ui.screener.pages.screener_session import activate_screener_page, deactivate_screener_page


class QuotesSessionLifecycleTests(unittest.TestCase):
    def test_activate_radar_page_short_circuit(self) -> None:
        page = MagicMock()
        page.config.use_radar_cards = True
        page.config.column_configurable = False
        page._table.sync_tail_columns_with_config.return_value = False
        page._radar_controller = MagicMock()

        activate_quotes_page(page)

        page._update_quote_source_label.assert_called_once()
        page._radar_controller.activate.assert_called_once()
        page.load_stock_list.assert_not_called()

    def test_deactivate_radar_page(self) -> None:
        page = MagicMock()
        page.config.use_radar_cards = True
        page._radar_controller = MagicMock()

        deactivate_quotes_page(page)

        page._radar_controller.deactivate.assert_called_once()
        self.assertFalse(page._active)
        page._save_splitter.assert_not_called()


class QuotesWorkerLifecycleTests(unittest.TestCase):
    @patch("vnpy_ashare.ui.quotes.page.session_lifecycle.teardown_quotes_page_workers")
    def test_deactivate_non_radar_calls_teardown(self, teardown: MagicMock) -> None:
        page = MagicMock()
        page.config.use_radar_cards = False

        deactivate_quotes_page(page)

        teardown.assert_called_once_with(page)


class ScreenerSessionLifecycleTests(unittest.TestCase):
    def test_activate_refreshes_sidebar_and_status(self) -> None:
        page = MagicMock()

        with patch("vnpy_ashare.ui.screener.pages.screener_session.sync_screener_page_context") as sync_ctx:
            activate_screener_page(page)

        page._reload_preset_combo.assert_called_once()
        page.run_sidebar.refresh.assert_called_once()
        page._status_controller.activate.assert_called_once()
        sync_ctx.assert_called_once_with(page.main_engine)
        self.assertTrue(page._active)

    def test_deactivate_cancels_workers(self) -> None:
        page = MagicMock()
        page._run_controller = MagicMock()
        page._download_worker = None
        page._batch_backtest_flow = MagicMock()

        deactivate_screener_page(page)

        page._run_controller.cancel_screening.assert_called_once()
        page._run_controller.release_workers.assert_called_once_with(timeout_ms=0)
        page._task_guard.end.assert_called_once()
        page._batch_backtest_flow.release_worker.assert_called_once()


if __name__ == "__main__":
    unittest.main()
