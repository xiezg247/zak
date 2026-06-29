"""雷达控制器性能相关行为：批量加载、共振防抖与 UI 错峰。"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from unittest.mock import MagicMock, patch

import pytest
from vnpy.trader.ui import QtWidgets

import tests._bootstrap  # noqa: F401


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
    controller._start_group_load = MagicMock()
    return controller, board, panel


def test_refresh_current_group_uses_batch_worker(qapp: QtWidgets.QApplication) -> None:
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
        controller.refresh_current_group()

    controller._start_group_load.assert_called_once()
    items = controller._start_group_load.call_args.args[0]
    assert [card_id for card_id, _kwargs in items] == [
        "market_emotion",
        "leader_pick",
        "watchlist_short_term",
    ]
    controller.refresh_card.assert_not_called()


def test_enqueue_single_card_still_uses_refresh_card(qapp: QtWidgets.QApplication) -> None:
    controller, _board, _panel = _make_controller(qapp)
    controller._enqueue_refresh_many([("leader_pick", {})])
    controller.refresh_card.assert_called_once_with("leader_pick", force_recompute=False, quote_only=False)
    controller._start_group_load.assert_not_called()


def test_on_card_loaded_debounces_resonance_sync(qapp: QtWidgets.QApplication) -> None:
    from vnpy_ashare.quotes.radar.loaders import RadarCardData

    controller, board, _panel = _make_controller(qapp)
    controller.refresh_card = controller.__class__.refresh_card  # restore real method not needed
    # Rebuild without mocking refresh_card
    page = QtWidgets.QWidget()
    board = MagicMock()
    board.current_mode.return_value = "statistical"
    board.current_group.return_value = "leader"
    from vnpy_ashare.ui.quotes.radar.controller import RadarController

    with patch.object(RadarController, "_setup_auto_refresh_timers"):
        controller = RadarController(page, board, resonance_panel=MagicMock())

    panel_sync_calls: list[int] = []

    def _panel_sync() -> None:
        panel_sync_calls.append(1)

    controller._sync_resonance_panel = _panel_sync  # type: ignore[method-assign]
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

    timers: list[object] = []

    def _capture_timer(_ms: int, callback) -> None:
        timers.append(callback)

    with patch.object(controller, "_schedule_resonance_sync", wraps=controller._schedule_resonance_sync):
        controller._on_card_loaded("market_emotion", data_a)
        controller._on_card_loaded("leader_pick", data_b)
        assert panel_sync_calls == []
        with patch("vnpy_ashare.ui.quotes.radar.controller.QtCore.QTimer.singleShot", side_effect=_capture_timer):
            controller._flush_resonance_sync()
        assert panel_sync_calls == []
        board.sync_resonance.assert_called_once()
        assert len(timers) == 1
        timers[0]()
        assert panel_sync_calls == [1]


def test_group_load_splits_viewport_priority(qapp: QtWidgets.QApplication) -> None:
    from vnpy_ashare.ui.quotes.radar.controller import RadarController

    page = QtWidgets.QWidget()
    board = MagicMock()
    board.current_mode.return_value = "statistical"
    board.current_group.return_value = "discovery"
    board.visible_card_ids_for_current_group.return_value = [
        "discovery_limit_ladder",
        "discovery_limit_break",
    ]

    with patch.object(RadarController, "_setup_auto_refresh_timers"):
        controller = RadarController(page, board, resonance_panel=MagicMock())

    controller._run_group_worker = MagicMock()
    items = [
        ("discovery_limit_ladder", {}),
        ("discovery_limit_break", {}),
        ("discovery_volume_surge", {}),
        ("discovery_moneyflow_intraday", {}),
    ]
    controller._start_group_load(items)
    controller._run_group_worker.assert_called_once()
    first_batch = controller._run_group_worker.call_args.args[0]
    assert {card_id for card_id, _kwargs in first_batch} == {
        "discovery_limit_ladder",
        "discovery_limit_break",
    }
    assert {card_id for card_id, _kwargs in controller._deferred_group_items} == {
        "discovery_volume_surge",
        "discovery_moneyflow_intraday",
    }
    assert not controller._deferred_tier_batches


def test_schedule_sibling_prefetch_queues_other_groups(qapp: QtWidgets.QApplication) -> None:
    from vnpy_ashare.ui.quotes.radar.controller import RadarController

    page = QtWidgets.QWidget()
    board = MagicMock()
    board.current_mode.return_value = "statistical"
    board.current_group.return_value = "leader"
    host = MagicMock()

    with patch.object(RadarController, "_setup_auto_refresh_timers"):
        controller = RadarController(page, board, resonance_panel=MagicMock())

    controller._find_main_window = MagicMock(return_value=host)
    kick_callbacks: list[object] = []

    def _capture_idle(_host, callback, **kwargs) -> None:
        kick_callbacks.append(callback)

    with patch(
        "vnpy_ashare.ui.quotes.radar.controller.run_when_idle",
        side_effect=_capture_idle,
    ):
        controller._schedule_sibling_prefetch()

    assert controller._prefetch_mode == "statistical"
    assert controller._prefetch_siblings == ["discovery", "portfolio"]
    assert len(kick_callbacks) == 1
    controller._start_prefetch_group = MagicMock()
    kick_callbacks[0]()
    controller._start_prefetch_group.assert_called_once()


def test_group_change_uses_cached_payload(qapp: QtWidgets.QApplication) -> None:
    from vnpy_ashare.quotes.radar.loaders import RadarCardData
    from vnpy_ashare.ui.quotes.radar.controller import RadarController

    page = QtWidgets.QWidget()
    board = MagicMock()
    board.current_mode.return_value = "statistical"
    board.current_group.return_value = "discovery"

    with patch.object(RadarController, "_setup_auto_refresh_timers"):
        controller = RadarController(page, board, resonance_panel=MagicMock())

    controller.refresh_current_group = MagicMock()
    controller._apply_group_from_cache = MagicMock()
    controller._start_auto_refresh = MagicMock()
    controller._last_payload = {
        "discovery_limit_ladder": RadarCardData(
            card_id="discovery_limit_ladder",
            title="发现·连板梯队",
            subtitle="",
            rows=(),
            empty_message="",
            updated_at="10:00",
        )
    }

    with patch(
        "vnpy_ashare.ui.quotes.radar.controller.list_radar_cards_for_group",
        return_value=[MagicMock(id="discovery_limit_ladder")],
    ):
        controller._on_board_group_changed("statistical", "discovery")

    controller._apply_group_from_cache.assert_called_once_with(["discovery_limit_ladder"])
    controller.refresh_current_group.assert_not_called()


def test_show_cached_cards_staggers_apply(qapp: QtWidgets.QApplication) -> None:
    from vnpy_ashare.quotes.radar.loaders import RadarCardData
    from vnpy_ashare.ui.quotes.radar.controller import RadarController

    page = QtWidgets.QWidget()
    board = MagicMock()

    with patch.object(RadarController, "_setup_auto_refresh_timers"):
        controller = RadarController(page, board, resonance_panel=MagicMock())

    controller._last_payload = {
        "market_emotion": RadarCardData(
            card_id="market_emotion",
            title="盘面·环境",
            subtitle="",
            rows=(),
            empty_message="无",
            updated_at="10:00",
        ),
        "leader_pick": RadarCardData(
            card_id="leader_pick",
            title="选股·龙头",
            subtitle="",
            rows=(),
            empty_message="无",
            updated_at="10:01",
        ),
    }
    controller._show_cached_cards(["market_emotion", "leader_pick"])
    board.apply_card.assert_called_once()
    assert controller._pending_cache_apply_queue == ["leader_pick"]


def test_start_group_load_splits_leader_priority(qapp: QtWidgets.QApplication) -> None:
    from vnpy_ashare.ui.quotes.radar.controller import RadarController

    page = QtWidgets.QWidget()
    board = MagicMock()
    board.visible_card_ids_for_current_group.return_value = {
        "market_emotion",
        "leader_pick",
        "watchlist_short_term",
    }

    with patch.object(RadarController, "_setup_auto_refresh_timers"):
        controller = RadarController(page, board, resonance_panel=MagicMock())

    controller._run_group_worker = MagicMock()
    items = [
        ("market_emotion", {}),
        ("leader_pick", {}),
        ("watchlist_short_term", {}),
    ]
    controller._start_group_load(items)

    controller._run_group_worker.assert_called_once()
    first_batch = controller._run_group_worker.call_args.args[0]
    assert [card_id for card_id, _kwargs in first_batch] == ["leader_pick"]
    assert len(controller._deferred_tier_batches) == 2
    assert [card_id for card_id, _kwargs in controller._deferred_tier_batches[0]] == ["watchlist_short_term"]
    assert [card_id for card_id, _kwargs in controller._deferred_tier_batches[1]] == ["market_emotion"]


def test_on_group_loaded_drains_tier_batches_before_prefetch(qapp: QtWidgets.QApplication) -> None:
    from vnpy_ashare.quotes.radar.loaders import RadarCardData
    from vnpy_ashare.ui.quotes.radar.controller import RadarController
    from vnpy_ashare.ui.quotes.radar.worker import RadarGroupLoadWorker

    page = QtWidgets.QWidget()
    board = MagicMock()
    board.visible_card_ids_for_current_group.return_value = {"leader_pick"}

    with patch.object(RadarController, "_setup_auto_refresh_timers"):
        controller = RadarController(page, board, resonance_panel=MagicMock())

    controller._deferred_tier_batches = [[("watchlist_short_term", {})]]
    controller._schedule_sibling_prefetch = MagicMock()
    controller._start_group_load = MagicMock()
    worker = MagicMock(spec=RadarGroupLoadWorker)
    controller._group_worker = worker

    data = RadarCardData(
        card_id="leader_pick",
        title="选股·龙头",
        subtitle="",
        rows=(),
        empty_message="",
        updated_at="10:00",
    )
    controller._on_group_loaded({"leader_pick": data}, {}, worker=worker)

    controller._start_group_load.assert_called_once_with([("watchlist_short_term", {})], skip_viewport_split=True)
    controller._schedule_sibling_prefetch.assert_not_called()


def test_quote_only_load_skips_resonance_panel_sync(qapp: QtWidgets.QApplication) -> None:
    from vnpy_ashare.quotes.radar.loaders import RadarCardData

    page = QtWidgets.QWidget()
    board = MagicMock()
    from vnpy_ashare.ui.quotes.radar.controller import RadarController

    with patch.object(RadarController, "_setup_auto_refresh_timers"):
        controller = RadarController(page, board, resonance_panel=MagicMock())

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
