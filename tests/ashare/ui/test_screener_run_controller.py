"""ScreenerRunController 单元测试。"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from vnpy_ashare.screener.run.runner import ScreenerRunResult
from vnpy_ashare.ui.screener.pages.screener_run_controller import ScreenerRunController


def _result(**kwargs) -> ScreenerRunResult:
    defaults = {
        "rows": [],
        "condition": "测试",
        "total_scanned": 0,
        "updated_at": "2026-06-23",
        "source": "quote",
        "columns": [],
    }
    defaults.update(kwargs)
    return ScreenerRunResult(**defaults)


class ScreenerRunControllerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.page = MagicMock()
        self.page._active = True
        self.page._task_guard = MagicMock()
        self.page._task_guard.active = False
        self.page._task_guard.cancelled = False
        self.page._task_lock_widgets.return_value = []
        self.page._build_request.return_value = (None, None)
        self.page._pending_industry = ""
        self.controller = ScreenerRunController(self.page)

    def test_run_screening_skips_when_request_invalid(self) -> None:
        self.controller.run_screening()
        self.page._task_guard.begin.assert_not_called()

    @patch("vnpy_ashare.ui.screener.pages.screener_run_controller.ScreenerRunWorker")
    def test_run_screening_starts_worker(self, worker_cls: MagicMock) -> None:
        from vnpy_ashare.screener.run.runner import ScreenerRequest

        request = ScreenerRequest(preset="涨幅榜", top_n=10)
        self.page._build_request.return_value = (request, None)
        worker = MagicMock()
        worker_cls.return_value = worker

        self.controller.run_screening()

        worker_cls.assert_called_once()
        worker.start.assert_called_once()
        self.assertIs(self.controller._worker, worker)

    def test_cancel_screening_requests_all_workers(self) -> None:
        workers = {attr: MagicMock() for attr in ScreenerRunController._SCREENING_WORKER_ATTRS}
        for attr, worker in workers.items():
            setattr(self.controller, attr, worker)

        self.controller.cancel_screening()

        for worker in workers.values():
            worker.request_cancel.assert_called_once()

    def test_on_radar_finished_applies_result(self) -> None:
        result = _result(condition="雷达共振")
        self.controller._radar_worker = MagicMock()

        self.controller._on_radar_finished(result)

        self.page._apply_screen_result.assert_called_once_with(result, trigger="radar")
        self.assertIsNone(self.controller._radar_worker)

    def test_on_radar_failed_shows_error(self) -> None:
        self.controller._radar_worker = MagicMock()

        self.controller._on_radar_failed("网络错误")

        self.page.run_output_panel.fail_run.assert_called_once_with("网络错误")
        self.page._toast.error.assert_called_once_with("网络错误")


if __name__ == "__main__":
    unittest.main()
