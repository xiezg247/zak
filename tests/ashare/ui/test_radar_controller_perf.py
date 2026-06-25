"""雷达控制器性能相关行为：共振防抖与错峰刷新。"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from unittest.mock import MagicMock, patch

import pytest
import tests._bootstrap  # noqa: F401
from vnpy.trader.ui import QtWidgets


@pytest.fixture(scope="module")
def qapp() -> QtWidgets.QApplication:
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app


def _make_controller(qapp: QtWidgets.QApplication) -> tuple[object, MagicMock, MagicMock]:
    from vnpy_ashare.ui.quotes.radar.controller import RadarController

    page = QtWidgets.QWidget()
    board = MagicMock()
    board.current_mode.return_value = "statistical"
    board.current_group.return_value = "leader"
    panel = MagicMock()

    with patch.object(RadarController, "_setup_auto_refresh_timers"):
        controller = RadarController(page, board, resonance_panel=panel)

    controller._board = board
    controller.refresh_card = MagicMock()
    return controller, board, panel


def test_refresh_current_group_staggers_card_starts(qapp: QtWidgets.QApplication) -> None:
    controller, _board, _panel = _make_controller(qapp)
    specs = [
        MagicMock(id="market_emotion"),
        MagicMock(id="leader_pick"),
        MagicMock(id="watchlist_short_term"),
    ]

    with patch(
        "vnpy_ashare.ui.quotes.radar.controller.list_radar_cards_for_group",
        return_value=specs,
    ):
        with patch(
            "vnpy_ashare.ui.quotes.radar.controller.QtCore.QTimer.start",
        ) as start_timer:
            controller.refresh_current_group()

    assert controller.refresh_card.call_count == 1
    assert controller.refresh_card.call_args.args[0] == "market_emotion"
    assert start_timer.call_count == 1

    controller._dequeue_refresh()
    assert controller.refresh_card.call_count == 2
    assert controller.refresh_card.call_args.args[0] == "leader_pick"

    controller._dequeue_refresh()
    assert controller.refresh_card.call_count == 3
    assert controller.refresh_card.call_args.args[0] == "watchlist_short_term"


def test_on_card_loaded_debounces_resonance_sync(qapp: QtWidgets.QApplication) -> None:
    from vnpy_ashare.quotes.radar.radar_loaders import RadarCardData

    controller, board, _panel = _make_controller(qapp)
    panel_sync_calls: list[int] = []

    def _flush() -> None:
        controller._cached_resonance = {"600000.SH": 2}
        board.sync_resonance(controller._cached_resonance)
        panel_sync_calls.append(1)

    controller._flush_resonance_sync = _flush  # type: ignore[method-assign]
    controller._update_status = MagicMock()

    data_a = RadarCardData(
        card_id="market_emotion",
        title="盘面·环境",
        subtitle="",
        rows=(),
        empty_message="",
        updated_at="10:00",
    )
    data_b = RadarCardData(
        card_id="leader_pick",
        title="选股·龙头",
        subtitle="",
        rows=(),
        empty_message="",
        updated_at="10:01",
    )

    with patch.object(controller, "_schedule_resonance_sync", wraps=controller._schedule_resonance_sync):
        controller._on_card_loaded("market_emotion", data_a)
        controller._on_card_loaded("leader_pick", data_b)
        assert panel_sync_calls == []
        controller._flush_resonance_sync()
        assert panel_sync_calls == [1]
        board.sync_resonance.assert_called_once()


def test_quote_only_load_skips_resonance_panel_sync(qapp: QtWidgets.QApplication) -> None:
    from vnpy_ashare.quotes.radar.radar_loaders import RadarCardData

    controller, board, _panel = _make_controller(qapp)
    controller._sync_resonance_panel = MagicMock()
    controller._schedule_resonance_sync = MagicMock()

    data = RadarCardData(
        card_id="market_emotion",
        title="盘面·环境",
        subtitle="",
        rows=(),
        empty_message="",
        updated_at="10:00",
    )
    controller._on_card_loaded("market_emotion", data, quote_only=True)

    board.apply_quote_update.assert_called_once()
    controller._schedule_resonance_sync.assert_not_called()
    controller._sync_resonance_panel.assert_not_called()
