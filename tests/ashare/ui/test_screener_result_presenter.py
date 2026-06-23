"""ScreenerResultPresenter 单元测试。"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from vnpy_ashare.screener.run.runner import ScreenerRunResult
from vnpy_ashare.ui.screener.pages.screener_result_presenter import ScreenerResultPresenter


def _result(**kwargs) -> ScreenerRunResult:
    defaults = {
        "rows": [{"symbol": "600519"}],
        "condition": "涨幅榜",
        "total_scanned": 100,
        "updated_at": "2026-06-23",
        "source": "quote",
        "columns": [],
    }
    defaults.update(kwargs)
    return ScreenerRunResult(**defaults)


class ScreenerResultPresenterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.page = MagicMock()
        self.page._results = []
        self.page._result_columns = []
        self.page._last_run_config = {}
        self.page._build_request.return_value = (MagicMock(), None)
        self.page._screening_service.return_value = MagicMock()
        self.presenter = ScreenerResultPresenter(self.page)

    @patch("vnpy_ashare.ui.screener.pages.screener_result_presenter.sync_screener_page_context")
    @patch("vnpy_ashare.ui.screener.pages.screener_result_presenter.apply_screener_results_view")
    def test_apply_screen_result_manual(self, apply_view: MagicMock, sync_ctx: MagicMock) -> None:
        service = self.page._screening_service.return_value
        service.resolve_export_columns.return_value = [("symbol", "代码")]
        service.format_source_tag.return_value = "Redis 行情"

        self.presenter.apply_screen_result(_result(), trigger="manual")

        service.save_manual_run.assert_called_once()
        apply_view.assert_called_once()
        self.page.run_output_panel.complete_run.assert_called_once()
        sync_ctx.assert_called_once_with(self.page.main_engine)
        self.page._toast.success.assert_called_once()

    @patch("vnpy_ashare.ui.screener.pages.screener_result_presenter.sync_screener_page_context")
    @patch("vnpy_ashare.ui.screener.pages.screener_result_presenter.apply_screener_results_view")
    def test_clear_loaded_run_view(self, apply_view: MagicMock, sync_ctx: MagicMock) -> None:
        self.presenter.clear_loaded_run_view()

        self.assertIsNone(self.page._loaded_run_id)
        self.assertEqual(self.page._results, [])
        apply_view.assert_called_once()
        self.page.result_insights.clear.assert_called_once()
        sync_ctx.assert_not_called()


if __name__ == "__main__":
    unittest.main()
