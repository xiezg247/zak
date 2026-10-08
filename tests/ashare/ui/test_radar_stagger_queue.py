"""错峰队列与防抖定时器测试。"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from vnpy.trader.ui import QtCore, QtWidgets

import tests._bootstrap  # noqa: F401


@pytest.fixture(scope="module")
def qapp() -> QtWidgets.QApplication:
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app


def test_stagger_queue_replace_kicks_first(qapp: QtWidgets.QApplication) -> None:
    from vnpy_ashare.ui.quotes.radar.stagger_queue import StaggerQueue

    parent = QtCore.QObject()
    seen: list[str] = []
    queue = StaggerQueue(parent, interval_ms=50, on_item=seen.append)
    queue.replace(["a", "b", "c"])
    assert seen == ["a"]
    assert queue.pending == ["b", "c"]


def test_stagger_queue_extend_unique_reorders(qapp: QtWidgets.QApplication) -> None:
    from vnpy_ashare.ui.quotes.radar.stagger_queue import StaggerQueue

    parent = QtCore.QObject()
    seen: list[str] = []
    queue = StaggerQueue(parent, interval_ms=50, on_item=seen.append)
    queue.replace(["a", "b"], kick=False)
    queue.extend_unique(["b", "c"], key=lambda x: x, kick=False)
    assert queue.pending == ["a", "b", "c"]


def test_stagger_queue_upsert_by_key_idle_kick(qapp: QtWidgets.QApplication) -> None:
    from vnpy_ashare.ui.quotes.radar.stagger_queue import StaggerQueue

    parent = QtCore.QObject()
    seen: list[tuple[str, int]] = []
    queue = StaggerQueue(parent, interval_ms=50, on_item=seen.append)
    queue.upsert_by_key([("a", 1), ("b", 1)], key=lambda item: item[0])
    assert seen == [("a", 1)]
    assert queue.pending == [("b", 1)]
    queue.upsert_by_key([("b", 2)], key=lambda item: item[0], kick_if_idle=False)
    assert queue.pending == [("b", 2)]


def test_debounced_call_reschedules(qapp: QtWidgets.QApplication) -> None:
    from vnpy_ashare.ui.quotes.radar.stagger_queue import DebouncedCall

    parent = QtCore.QObject()
    hits: list[int] = []
    debounced = DebouncedCall(parent, interval_ms=30, callback=lambda: hits.append(1))
    debounced.schedule()
    debounced.schedule()
    assert hits == []
    debounced.stop()
