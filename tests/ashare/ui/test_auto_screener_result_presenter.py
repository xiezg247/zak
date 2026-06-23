"""AutoScreenerResultPresenter 单元测试。"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from vnpy_ashare.screener.run.runner import ScreenerRunResult
from vnpy_ashare.ui.screener.pages.auto_screener_result_presenter import AutoScreenerResultPresenter


def _result(**kwargs) -> ScreenerRunResult:
    defaults = {
        "rows": [{"symbol": "600519"}],
        "condition": "测试配方",
        "total_scanned": 100,
        "updated_at": "2026-06-23",
        "source": "quote",
        "columns": [],
    }
    defaults.update(kwargs)
    return ScreenerRunResult(**defaults)


class AutoScreenerResultPresenterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.page = MagicMock()
        self.page._results = []
        self.page._result_columns = []
        self.page._last_run_config = {}
        self.page._screening_service.return_value = MagicMock()
        self.presenter = AutoScreenerResultPresenter(self.page)

    @patch("vnpy_ashare.ui.screener.pages.auto_screener_result_presenter.apply_screener_results_view")
    def test_apply_result_updates_table_and_context(self, apply_view: MagicMock) -> None:
        result = _result()
        service = self.page._screening_service.return_value
        service.resolve_export_columns.return_value = [("symbol", "代码")]

        summary = self.presenter.apply_result(result, config={"trigger": "manual", "recipe_id": "r1"})

        apply_view.assert_called_once()
        service.set_screening_results.assert_called_once()
        self.page.result_insights.apply.assert_called_once()
        self.assertIn("命中 1 条", summary)

    @patch("vnpy_ashare.ui.screener.pages.auto_screener_result_presenter.sync_screener_page_context")
    @patch("vnpy_ashare.ui.screener.pages.auto_screener_result_presenter.apply_screener_results_view")
    def test_load_historical_run_missing_record(self, apply_view: MagicMock, sync_ctx: MagicMock) -> None:
        self.page._screening_service.return_value.get_run_record.return_value = None

        self.presenter.load_historical_run("missing-id")

        self.page._append_action_log.assert_called_once()
        apply_view.assert_called_once()
        sync_ctx.assert_not_called()

    @patch("vnpy_ashare.ui.screener.pages.auto_screener_result_presenter.apply_screener_results_view")
    def test_clear_loaded_run_view(self, apply_view: MagicMock) -> None:
        self.presenter.clear_loaded_run_view()

        self.assertIsNone(self.page._loaded_run_id)
        self.assertEqual(self.page._results, [])
        apply_view.assert_called_once()
        self.page.result_insights.clear.assert_called_once()


if __name__ == "__main__":
    unittest.main()
