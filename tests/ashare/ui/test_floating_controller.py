"""悬浮球协调层单元测试。"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from vnpy.trader.ui import QtWidgets

from vnpy_ashare.ui.shell.floating_controller import FLOATING_ORB_PAGE_KEYS, FloatingAiController


class FloatingControllerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def test_page_whitelist(self) -> None:
        self.assertTrue(FloatingAiController.is_page_allowed("watchlist"))
        self.assertTrue(FloatingAiController.is_page_allowed("screener"))
        self.assertFalse(FloatingAiController.is_page_allowed("cta_backtest"))
        self.assertEqual(
            FLOATING_ORB_PAGE_KEYS,
            frozenset({"watchlist", "market", "radar", "local", "screener", "auto_screener"}),
        )

    def test_load_orb_user_hidden(self) -> None:
        with patch("vnpy_ashare.ui.shell.floating_controller.QtCore.QSettings") as mock_settings:
            mock_settings.return_value.value.return_value = True
            self.assertTrue(FloatingAiController._load_orb_user_hidden())

            mock_settings.return_value.value.return_value = "true"
            self.assertTrue(FloatingAiController._load_orb_user_hidden())

            mock_settings.return_value.value.return_value = False
            self.assertFalse(FloatingAiController._load_orb_user_hidden())

    def _bare_controller(self, page_key: str) -> FloatingAiController:
        host = QtWidgets.QWidget()
        controller = FloatingAiController(host, MagicMock())
        controller._orb = MagicMock()
        controller._panel = None
        controller._orb_user_hidden = False
        controller.bind_page_key(lambda: page_key)
        return controller

    def test_notify_attention_skips_when_not_on_screener(self) -> None:
        controller = self._bare_controller("watchlist")
        with patch.object(controller, "refresh_context"):
            controller.notify_attention("screener")
        controller._orb.play_attention_pulse.assert_not_called()

    def test_notify_attention_pulses_on_screener(self) -> None:
        controller = self._bare_controller("screener")
        controller._orb.isVisible.return_value = True
        with patch.object(controller, "refresh_context"):
            controller.notify_attention("screener")
        controller._orb.play_attention_pulse.assert_called_once()

    def test_notify_attention_skips_auto_screener_when_not_on_page(self) -> None:
        controller = self._bare_controller("watchlist")
        with patch.object(controller, "refresh_context"):
            controller.notify_attention("auto_screener")
        controller._orb.play_attention_pulse.assert_not_called()

    def test_notify_attention_pulses_on_auto_screener(self) -> None:
        controller = self._bare_controller("auto_screener")
        controller._orb.isVisible.return_value = True
        with patch.object(controller, "refresh_context"):
            controller.notify_attention("auto_screener")
        controller._orb.play_attention_pulse.assert_called_once()


if __name__ == "__main__":
    unittest.main()
