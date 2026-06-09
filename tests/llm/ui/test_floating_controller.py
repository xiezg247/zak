"""FloatingAiController 协调层单元测试。"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from vnpy.trader.ui import QtWidgets

from vnpy_ashare.events import AskAiRequest
from vnpy_ashare.ui.floating_controller import FLOATING_ORB_PAGE_KEYS, FloatingAiController


class FloatingAiControllerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def setUp(self) -> None:
        self._shell = QtWidgets.QWidget()
        self._shell.show()

    def _make_controller(self) -> FloatingAiController:
        host = QtWidgets.QWidget()
        host._open_ai_page = MagicMock()
        host._open_ai_tools_dialog = MagicMock()
        host._show_page = MagicMock()
        host._nav_index_for_key = MagicMock(return_value=0)
        host._page_before_ai = 0

        engine = MagicMock()
        signals = MagicMock()
        engine.signals = signals
        engine.is_busy.return_value = False
        engine.open_session_for_ask.return_value = "session-1"

        controller = FloatingAiController(host, engine)
        controller.bind_page_key(lambda: "watchlist")
        mock_panel = MagicMock()
        with (
            patch(
                "vnpy_ashare.ui.floating_controller.FloatingAiPanel",
                return_value=mock_panel,
            ),
            patch.object(
                FloatingAiController,
                "_load_orb_user_hidden",
                return_value=False,
            ),
        ):
            controller.init(self._shell)
        controller._panel = mock_panel
        return controller

    def test_page_whitelist(self) -> None:
        self.assertEqual(FLOATING_ORB_PAGE_KEYS, frozenset({"watchlist", "market", "local", "screener"}))
        self.assertTrue(FloatingAiController.is_page_allowed("watchlist"))
        self.assertFalse(FloatingAiController.is_page_allowed("cta_backtest"))

    def test_on_page_changed_shows_or_hides_orb(self) -> None:
        controller = self._make_controller()
        orb = controller.orb
        assert orb is not None
        controller.on_page_changed("watchlist")
        self.assertTrue(orb.isVisible())
        controller.on_page_changed("cta_backtest")
        self.assertFalse(orb.isVisible())

    def test_orb_user_hidden_persists_across_page_change(self) -> None:
        controller = self._make_controller()
        orb = controller.orb
        assert orb is not None
        with patch.object(controller, "_save_orb_user_hidden") as save_hidden:
            controller.hide_orb(user_initiated=True)
            save_hidden.assert_called_once()
        self.assertTrue(controller._orb_user_hidden)
        controller.on_page_changed("watchlist")
        self.assertFalse(orb.isVisible())
        controller.on_page_changed("market")
        self.assertFalse(orb.isVisible())

    def test_handle_ask_ai_opens_panel_with_scene(self) -> None:
        controller = self._make_controller()
        panel = controller.panel
        assert panel is not None
        panel.submit_prompt = MagicMock()
        controller.show_panel = MagicMock(wraps=controller.show_panel)

        controller.handle_ask_ai(
            AskAiRequest(
                prompt="诊断一下",
                source_page="自选",
                scene="自选 · 贵州茅台",
                action_id="diagnose_full",
            )
        )

        controller.show_panel.assert_called_once()
        _, kwargs = controller.show_panel.call_args
        self.assertEqual(kwargs["scene"], "自选 · 贵州茅台")
        panel.submit_prompt.assert_called_once_with(
            "诊断一下",
            auto_send=False,
            action_id="diagnose_full",
        )

    def test_scene_from_context(self) -> None:
        from vnpy_ashare.ai.context import AiContextData

        controller = self._make_controller()
        with patch(
            "vnpy_ashare.ai.context_store.get_ai_context",
            return_value=AiContextData(
                page="市场",
                symbol="600519",
                exchange="上交所",
                name="贵州茅台",
                badge="市场",
                chip_text="市场 · 贵州茅台 · +2.3%",
            ),
        ):
            scene = controller._scene_from_context()
        self.assertEqual(scene, "市场 · 贵州茅台")


if __name__ == "__main__":
    unittest.main()
