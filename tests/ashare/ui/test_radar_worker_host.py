"""雷达 WorkerHost 生命周期测试。"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from vnpy.trader.ui import QtWidgets

import tests._bootstrap  # noqa: F401


@pytest.fixture(scope="module")
def qapp() -> QtWidgets.QApplication:
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app


def test_start_card_wires_finished_then_release(qapp: QtWidgets.QApplication) -> None:
    from vnpy_ashare.ui.quotes.radar.worker_host import RadarWorkerHost

    host = RadarWorkerHost()
    worker = MagicMock()
    worker.card_id = "leader_pick"
    worker.finished = MagicMock()
    worker.failed = MagicMock()

    finished_calls: list[tuple] = []
    failed_calls: list[tuple] = []

    with patch("vnpy_ashare.ui.quotes.radar.worker_host.release_thread") as release:
        host.start_card(
            worker,
            on_finished=lambda *args: finished_calls.append(args),
            on_failed=lambda *args: failed_calls.append(args),
        )
        worker.start.assert_called_once()
        assert worker.finished.connect.call_count == 1
        assert worker.failed.connect.call_count == 1

        finished_slot = worker.finished.connect.call_args.args[0]
        finished_slot("leader_pick", object(), False)
        assert len(finished_calls) == 1
        release.assert_called()
        assert not host.card_is_active("leader_pick")


def test_cancel_all_clears_group_and_cards(qapp: QtWidgets.QApplication) -> None:
    from vnpy_ashare.ui.quotes.radar.worker_host import RadarWorkerHost

    host = RadarWorkerHost()
    card = MagicMock()
    card.card_id = "a"
    card.finished = MagicMock()
    card.failed = MagicMock()
    group = MagicMock()
    group.card_ids = frozenset({"a"})
    group.finished = MagicMock()
    group.failed = MagicMock()

    with patch("vnpy_ashare.ui.quotes.radar.worker_host.release_thread"):
        host.start_card(card, on_finished=lambda *_: None, on_failed=lambda *_: None)
        host.start_group(group, on_finished=lambda *_: None, on_failed=lambda *_: None)
        host.cancel_all()
        card.request_cancel.assert_called()
        group.request_cancel.assert_called()
        assert host.group is None


def test_group_covers_card(qapp: QtWidgets.QApplication) -> None:
    from vnpy_ashare.ui.quotes.radar.worker_host import RadarWorkerHost

    host = RadarWorkerHost()
    worker = MagicMock()
    worker.card_ids = frozenset({"leader_pick", "market_emotion"})
    with patch("vnpy_ashare.ui.quotes.radar.worker_host.thread_is_active", return_value=True):
        host.group = worker
        assert host.group_covers_card("leader_pick")
        assert not host.group_covers_card("other")
