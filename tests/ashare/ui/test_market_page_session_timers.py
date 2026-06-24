"""市场页非交易时段定时器门禁测试。"""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from vnpy.trader.ui import QtWidgets

from vnpy_ashare.ui.quotes.market_discovery.controller import MarketDiscoveryController
from vnpy_ashare.ui.quotes.market_overview.controller import MarketOverviewController


def _ensure_qapp() -> None:
    if QtWidgets.QApplication.instance() is None:
        QtWidgets.QApplication([])


class MarketPageSessionTimerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        _ensure_qapp()

    def _overview_controller(self) -> MarketOverviewController:
        page = QtWidgets.QWidget()
        page._actions = None  # type: ignore[attr-defined]
        page._market_industry_filter = None  # type: ignore[attr-defined]
        page.industry_filter = None  # type: ignore[attr-defined]
        page.set_market_industry_filter = MagicMock()  # type: ignore[attr-defined]
        page.status_label = SimpleNamespace(setText=MagicMock())  # type: ignore[attr-defined]
        panel = MagicMock()
        panel.sector_selected = MagicMock()
        panel.industry_filter_cleared = MagicMock()
        panel.sector_flow_requested = MagicMock()
        return MarketOverviewController(page, panel)  # type: ignore[arg-type]

    def _discovery_controller(self) -> MarketDiscoveryController:
        page = QtWidgets.QWidget()
        page._table = SimpleNamespace(focus_market_symbol=MagicMock(return_value=False))  # type: ignore[attr-defined]
        strip = MagicMock()
        strip.row_activated = MagicMock()
        return MarketDiscoveryController(page, strip)  # type: ignore[arg-type]

    @patch(
        "vnpy_ashare.ui.quotes.market_overview.controller.is_ashare_trading_session",
        return_value=False,
    )
    def test_overview_activate_outside_session_stops_refresh_timer(self, _mock: MagicMock) -> None:
        controller = self._overview_controller()
        controller.activate()
        self.assertFalse(controller._refresh_timer.isActive())
        self.assertTrue(controller._session_timer.isActive())

    @patch(
        "vnpy_ashare.ui.quotes.market_overview.controller.is_ashare_trading_session",
        return_value=True,
    )
    def test_overview_activate_in_session_starts_refresh_timer(self, _mock: MagicMock) -> None:
        controller = self._overview_controller()
        controller.activate()
        self.assertTrue(controller._refresh_timer.isActive())

    @patch(
        "vnpy_ashare.ui.quotes.market_discovery.controller.is_ashare_trading_session",
        return_value=False,
    )
    def test_discovery_activate_outside_session_stops_refresh_timer(self, _mock: MagicMock) -> None:
        controller = self._discovery_controller()
        controller.activate()
        self.assertFalse(controller._refresh_timer.isActive())
        self.assertTrue(controller._session_timer.isActive())

    @patch(
        "vnpy_ashare.ui.quotes.market_discovery.controller.is_ashare_trading_session",
        return_value=True,
    )
    def test_discovery_activate_in_session_starts_refresh_timer(self, _mock: MagicMock) -> None:
        controller = self._discovery_controller()
        controller.activate()
        self.assertTrue(controller._refresh_timer.isActive())


if __name__ == "__main__":
    unittest.main()
