"""AI 输入框 Enter 发送行为测试。"""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from vnpy.trader.ui import QtCore, QtGui, QtWidgets

from vnpy_llm.ui.panel import AiChatPanel, AiInputEdit


class AiInputEnterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def _make_panel(self) -> AiChatPanel:
        engine = MagicMock()
        engine.config.configured = True
        engine.config.model = "test"
        engine.get_messages.return_value = []
        engine.get_tools_status.return_value = MagicMock(
            ready_count=0,
            total_count=0,
            skills=[],
            mcp=[],
        )
        patches = [
            patch.object(AiChatPanel, "_connect_signals"),
            patch.object(AiChatPanel, "_refresh_messages"),
            patch.object(AiChatPanel, "_update_model_action"),
            patch("vnpy_llm.ui.floating_actions.build_quick_actions_for_panel", return_value=[]),
            patch("vnpy_ashare.ai.session_context.get_ai_context", return_value=MagicMock(page="AI 助手")),
        ]
        for item in patches:
            item.start()
        self.addCleanup(lambda: [p.stop() for p in patches])
        return AiChatPanel(MagicMock(), compact=False)

    def test_enter_sends_when_completion_visible_but_unfocused(self) -> None:
        panel = self._make_panel()
        panel.set_input_text("帮我分析600519的基本面")
        panel._completion_popup.show()
        self.assertTrue(panel._completion_popup.isVisible())
        self.assertFalse(panel._completion_popup.hasFocus())

        sent: list[str] = []

        def capture_send() -> None:
            sent.append(panel.input_box.toPlainText())

        panel._on_send = capture_send  # type: ignore[method-assign]
        panel._on_input_enter(newline=False)

        self.assertEqual(sent, ["帮我分析600519的基本面"])
        self.assertFalse(panel._completion_popup.isVisible())

    def test_enter_selects_completion_when_popup_focused(self) -> None:
        panel = self._make_panel()
        panel.set_input_text("600519")
        panel._completion_popup.clear()
        panel._completion_popup.addItem("诊断600519")
        panel._completion_popup.item(0).setData(
            QtCore.Qt.ItemDataRole.UserRole,
            "请诊断600519",
        )
        panel._completion_popup.show()
        panel._completion_popup.setFocus()

        panel._on_input_enter(newline=False)
        self.assertEqual(panel.input_box.toPlainText(), "请诊断600519")

    def test_input_edit_emits_enter_signal(self) -> None:
        edit = AiInputEdit()
        received: list[bool] = []
        edit.enter_pressed.connect(received.append)
        event = QtGui.QKeyEvent(
            QtCore.QEvent.Type.KeyPress,
            QtCore.Qt.Key.Key_Return,
            QtCore.Qt.KeyboardModifier.NoModifier,
        )
        QtWidgets.QApplication.sendEvent(edit, event)
        self.assertEqual(received, [False])

    def test_handle_input_return_on_viewport(self) -> None:
        panel = self._make_panel()
        panel.set_input_text("测试发送")
        sent: list[str] = []
        panel._on_send = lambda: sent.append(panel.input_box.toPlainText())  # type: ignore[method-assign]

        event = QtGui.QKeyEvent(
            QtCore.QEvent.Type.KeyPress,
            QtCore.Qt.Key.Key_Return,
            QtCore.Qt.KeyboardModifier.NoModifier,
        )
        handled = panel._handle_input_return(event)
        self.assertTrue(handled)
        self.assertEqual(sent, ["测试发送"])


if __name__ == "__main__":
    unittest.main()
