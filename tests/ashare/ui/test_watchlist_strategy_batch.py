"""WatchlistStrategyBatchCoordinator 测试。"""

from __future__ import annotations

import sys
import unittest
from unittest.mock import MagicMock, patch

import tests._bootstrap  # noqa: F401
from vnpy.trader.ui import QtWidgets
from vnpy_ashare.config.preferences.watchlist_signal import WatchlistSignalConfig
from vnpy_ashare.ui.quotes.watchlist.strategy_batch import WatchlistStrategyBatchCoordinator


def _config(*, class_name: str = "AshareDoubleMaStrategy", fast: int = 10, slow: int = 20) -> WatchlistSignalConfig:
    return WatchlistSignalConfig(class_name=class_name, fast_window=fast, slow_window=slow).normalized()


class WatchlistStrategyBatchCoordinatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if QtWidgets.QApplication.instance() is None:
            cls._app = QtWidgets.QApplication(sys.argv)
        else:
            cls._app = QtWidgets.QApplication.instance()

    def _page(self) -> MagicMock:
        page = MagicMock()
        page._active = True
        page._retired_workers = []
        page._get_analysis_service.return_value = MagicMock()
        return page

    def test_merge_same_config_submissions(self) -> None:
        page = self._page()
        coord = WatchlistStrategyBatchCoordinator(page)
        config = _config()
        completed: list[str] = []

        coord.submit(
            zone="signal",
            symbols=["600519.SSE"],
            config=config,
            on_complete=lambda cache: completed.append(f"signal:{len(cache)}"),
            on_failed=lambda _msg: None,
        )
        coord.submit(
            zone="position",
            symbols=["600519.SSE", "000001.SZSE"],
            config=config,
            on_complete=lambda cache: completed.append(f"position:{len(cache)}"),
            on_failed=lambda _msg: None,
        )

        merged = coord._merge_jobs(coord._pending_jobs)
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0].symbols, {"600519.SSE", "000001.SZSE"})
        self.assertEqual(len(merged[0].jobs), 2)

    def test_merge_different_config_keeps_separate(self) -> None:
        page = self._page()
        coord = WatchlistStrategyBatchCoordinator(page)
        from vnpy_ashare.ui.quotes.watchlist.strategy_batch import _BatchJob

        batch_jobs = [
            _BatchJob("signal", ["600519.SSE"], _config(fast=10), lambda _c: None, lambda _m: None),
            _BatchJob("position", ["600519.SSE"], _config(fast=5), lambda _c: None, lambda _m: None),
        ]
        merged = coord._merge_jobs(batch_jobs)
        self.assertEqual(len(merged), 2)

    def test_is_refreshing_false_after_service_unavailable(self) -> None:
        page = self._page()
        page._get_analysis_service.return_value = None
        coord = WatchlistStrategyBatchCoordinator(page)
        config = _config()
        failed: list[str] = []

        coord.submit(
            zone="signal",
            symbols=["600519.SSE"],
            config=config,
            on_complete=lambda _cache: None,
            on_failed=lambda msg: failed.append(msg),
        )
        self._app.processEvents()

        self.assertFalse(coord.is_refreshing_zone("signal"))
        self.assertEqual(failed, ["analysis service unavailable"])

    @patch("vnpy_ashare.ui.quotes.watchlist.strategy_batch.WatchlistSignalWorker")
    def test_start_merged_runs_single_worker(self, worker_cls: MagicMock) -> None:
        page = self._page()
        coord = WatchlistStrategyBatchCoordinator(page)
        config = _config()
        worker = MagicMock()
        worker.isRunning.return_value = False
        worker_cls.return_value = worker

        from vnpy_ashare.ui.quotes.watchlist.strategy_batch import _BatchJob, _MergedBatch

        signal_done: list[int] = []
        position_done: list[int] = []
        merged = _MergedBatch(
            config=config,
            symbols={"600519.SSE"},
            jobs=[
                _BatchJob(
                    "signal",
                    ["600519.SSE"],
                    config,
                    lambda cache: signal_done.append(len(cache)),
                    lambda _m: None,
                ),
                _BatchJob(
                    "position",
                    ["600519.SSE"],
                    config,
                    lambda cache: position_done.append(len(cache)),
                    lambda _m: None,
                ),
            ],
        )

        coord._start_merged(merged)

        worker_cls.assert_called_once()
        finished = worker.finished.connect.call_args[0][0]
        from vnpy_ashare.ui.quotes.watchlist_signals.worker import WatchlistSignalWorkerPayload

        finished(WatchlistSignalWorkerPayload(signals={"600519.SSE": object()}))
        self.assertEqual(signal_done, [1])
        self.assertEqual(position_done, [1])


if __name__ == "__main__":
    unittest.main()
