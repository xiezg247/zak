"""雷达信号绑定表测试。"""

from __future__ import annotations

from unittest.mock import MagicMock

from vnpy_ashare.ui.quotes.radar.signal_wiring import BOARD_WIRING, PANEL_WIRING, bind_signals


def test_bind_signals_connects_all_handlers() -> None:
    source = MagicMock()
    owner = MagicMock()
    wiring = (("row_activated", "_on_row_activated"), ("ai_requested", "request_card_ai"))
    bind_signals(source, owner, wiring)
    source.row_activated.connect.assert_called_once_with(owner._on_row_activated)
    source.ai_requested.connect.assert_called_once_with(owner.request_card_ai)


def test_board_and_panel_wiring_handlers_exist_on_controller() -> None:
    from vnpy_ashare.ui.quotes.radar.controller import RadarController

    for _signal, handler in BOARD_WIRING + PANEL_WIRING:
        assert callable(getattr(RadarController, handler, None)), handler
