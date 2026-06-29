"""雷达加载协作式取消测试。"""

from __future__ import annotations

from unittest.mock import patch

import tests._bootstrap  # noqa: F401
from vnpy_ashare.quotes.radar.loaders.cancel import bind_radar_load_cancel, radar_load_cancelled, raise_if_radar_load_cancelled
from vnpy_ashare.quotes.radar.loaders.load import load_radar_cards_batch


def test_radar_load_cancel_context() -> None:
    cancelled = False
    reset = bind_radar_load_cancel(lambda: cancelled)
    try:
        assert not radar_load_cancelled()
        cancelled = True
        assert radar_load_cancelled()
        try:
            raise_if_radar_load_cancelled()
            raised = False
        except Exception:
            raised = True
        assert raised
    finally:
        reset()
    assert not radar_load_cancelled()


def test_load_radar_cards_batch_aborts_when_cancelled() -> None:
    with patch(
        "vnpy_ashare.quotes.radar.loaders.load._load_radar_cards_in_context",
    ) as load_ctx:
        cancelled = True
        reset = bind_radar_load_cancel(lambda: cancelled)
        try:
            loaded, errors = load_radar_cards_batch([("leader_pick", {})])
        finally:
            reset()
    assert loaded == {}
    assert errors == {}
    load_ctx.assert_not_called()
