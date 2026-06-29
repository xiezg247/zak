"""市场页 Worker 协作式取消测试。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import tests._bootstrap  # noqa: F401
from vnpy_ashare.ui.quotes.market_overview.worker import MarketOverviewLoadWorker
from vnpy_ashare.ui.quotes.page.worker_lifecycle import wait_worker_release
from vnpy_ashare.ui.quotes.workers.quotes_workers.market import MarketPageLoadWorker


def test_wait_worker_release_requests_cancel() -> None:
    worker = MagicMock()
    page = MagicMock()
    page._retired_workers = []
    page._market_worker = worker

    wait_worker_release(page, "_market_worker", timeout_ms=0)

    worker.request_cancel.assert_called_once()
    assert page._market_worker is None


def test_market_page_worker_emits_cancelled_when_requested_early() -> None:
    worker = MarketPageLoadWorker(keyword="", page=0, page_size=50)
    worker.request_cancel()
    signals: list[str] = []
    worker.failed.connect(signals.append)

    worker.run()

    assert signals == ["已取消"]


def test_market_overview_worker_skips_emit_when_cancelled() -> None:
    worker = MarketOverviewLoadWorker(intraday=True, force=False)
    finished: list[object] = []
    failed: list[str] = []
    worker.finished.connect(finished.append)
    worker.failed.connect(failed.append)

    with patch(
        "vnpy_ashare.ui.quotes.market_overview.worker.load_market_overview",
        return_value=object(),
    ) as load_mock:
        worker.request_cancel()
        worker.run()

    load_mock.assert_not_called()
    assert finished == []
    assert failed == ["已取消"]
