"""AutoScreenerRunController 单元测试。"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from vnpy_ashare.screener.run.runner import ScreenerRunResult
from vnpy_ashare.ui.screener.pages.auto_screener_run_controller import AutoScreenerRunController


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


class AutoScreenerRunControllerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.page = MagicMock()
        self.page._active = True
        self.page._task_guard = MagicMock()
        self.page._task_guard.active = False
        self.page._task_guard.cancelled = False
        self.page._task_lock_widgets.return_value = []
        self.page.recipe_panel._run_btn = MagicMock()
        self.page.recipe_panel._run_recipe = MagicMock()
        self.page.recipe_panel._top_n_spin.value.return_value = 20
        self.page._result_presenter.apply_result.return_value = "summary"
        self.page._screening_service.return_value = MagicMock()
        self.controller = AutoScreenerRunController(self.page)

    @patch("vnpy_ashare.ui.screener.pages.auto_screener_run_controller.ScreenerRecipeRunWorker")
    def test_run_recipe_starts_worker(self, worker_cls: MagicMock) -> None:
        worker = MagicMock()
        worker_cls.return_value = worker
        recipe = MagicMock(name="测试配方", top_n=10)

        self.controller.run_recipe(recipe, "recipe-1")

        worker_cls.assert_called_once_with(recipe, "recipe-1")
        worker.start.assert_called_once()
        self.assertIs(self.controller._recipe_worker, worker)

    def test_cancel_runs_requests_all_workers(self) -> None:
        workers = {attr: MagicMock() for attr in AutoScreenerRunController._RUN_WORKER_ATTRS}
        for attr, worker in workers.items():
            setattr(self.controller, attr, worker)

        self.controller.cancel_runs()

        for worker in workers.values():
            worker.request_cancel.assert_called_once()

    @patch("vnpy_ashare.ui.screener.pages.auto_screener_run_controller.enrich_condition_run")
    @patch("vnpy_ashare.ui.screener.pages.auto_screener_run_controller.sync_screener_page_context")
    def test_on_radar_finished_applies_result(self, sync_ctx: MagicMock, enrich: MagicMock) -> None:
        enrich.return_value = [{"symbol": "600519"}]
        result = _result(condition="雷达共振")
        self.controller._radar_worker = MagicMock()

        self.controller._on_radar_finished(result)

        self.page._result_presenter.apply_result.assert_called_once()
        self.page.run_output_panel.complete_run.assert_called_once()
        sync_ctx.assert_called_once_with(self.page.main_engine)
        self.assertIsNone(self.controller._radar_worker)

    def test_on_radar_failed_shows_error(self) -> None:
        self.controller._radar_worker = MagicMock()

        self.controller._on_radar_failed("网络错误")

        self.page.run_output_panel.fail_run.assert_called_once_with("网络错误")
        self.page._toast.error.assert_called_once_with("网络错误")


if __name__ == "__main__":
    unittest.main()
