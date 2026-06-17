"""TickFlow WebSocket 桥接测试。"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from vnpy.trader.ui import QtWidgets

import vnpy_ashare.integrations.tickflow.stream as tickflow_stream_module
from vnpy_ashare.integrations.tickflow.stream import TickflowStreamBridge, can_use_tickflow_stream


class TickflowStreamBridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def test_set_quote_symbols_updates_subscription(self) -> None:
        bridge = TickflowStreamBridge()
        mock_stream = MagicMock()
        bridge._stream = mock_stream
        bridge._quote_symbols = {"600000.SH"}

        bridge.set_quote_symbols(["600519.SH", "600000.SH"])

        mock_stream.unsubscribe.assert_not_called()
        mock_stream.subscribe.assert_called_once_with("quotes", ["600519.SH"])
        self.assertEqual(bridge._quote_symbols, {"600519.SH", "600000.SH"})

    def test_set_depth_symbol(self) -> None:
        bridge = TickflowStreamBridge()
        mock_stream = MagicMock()
        bridge._stream = mock_stream
        bridge._depth_symbol = "600000.SH"

        bridge.set_depth_symbol("600519.SH")

        mock_stream.unsubscribe.assert_called_once_with("depth", ["600000.SH"])
        mock_stream.subscribe.assert_called_once_with("depth", ["600519.SH"])

    @patch("vnpy_ashare.integrations.tickflow.stream.get_tickflow_client")
    def test_start_subscribes_pending_symbols(self, mock_get_client: MagicMock) -> None:
        mock_stream = MagicMock()
        mock_client = MagicMock()
        mock_client.stream = mock_stream
        mock_get_client.return_value = mock_client

        bridge = TickflowStreamBridge()
        bridge.set_quote_symbols(["600519.SH"])
        bridge.set_depth_symbol("600519.SH")
        bridge.start()

        mock_stream.subscribe.assert_any_call("quotes", ["600519.SH"])
        mock_stream.subscribe.assert_any_call("depth", ["600519.SH"])
        mock_stream.connect.assert_called_once_with(block=False)
        self.assertFalse(bridge.is_connected)

    def test_fatal_error_disables_stream(self) -> None:
        bridge = TickflowStreamBridge()
        mock_stream = MagicMock()
        bridge._stream = mock_stream
        bridge._connected = True

        bridge._handle_stream_error("connecting through a SOCKS proxy requires python-socks")

        mock_stream.close.assert_called_once()
        self.assertTrue(bridge._disabled)
        self.assertFalse(bridge.is_connected)

    @patch.dict("os.environ", {"ALL_PROXY": "socks5://127.0.0.1:7890"}, clear=False)
    def test_can_use_stream_without_python_socks(self) -> None:
        with patch.object(tickflow_stream_module.importlib.util, "find_spec", return_value=None):
            self.assertFalse(can_use_tickflow_stream())

    def test_shutdown_stream_joins_background_thread(self) -> None:
        bridge = TickflowStreamBridge()
        mock_stream = MagicMock()
        thread = MagicMock()
        thread.is_alive.return_value = True
        thread.join = MagicMock()
        mock_stream._thread = thread
        mock_stream._inner = MagicMock()
        bridge._stream = mock_stream

        bridge._shutdown_stream()

        mock_stream.close.assert_called_once()
        thread.join.assert_called_once_with(timeout=tickflow_stream_module._STREAM_SHUTDOWN_JOIN_TIMEOUT_SEC)
        self.assertTrue(bridge._disabled)
        self.assertIsNone(bridge._stream)

    def test_shutdown_all_tickflow_streams(self) -> None:
        bridge = TickflowStreamBridge()
        mock_stream = MagicMock()
        bridge._stream = mock_stream

        tickflow_stream_module.shutdown_all_tickflow_streams()

        mock_stream.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
