"""MCP 常驻 event loop 测试。"""

from __future__ import annotations

import unittest
from unittest.mock import patch

import tests._bootstrap  # noqa: F401
from vnpy_mcp.remote import client


class McpClientLoopTests(unittest.TestCase):
    def test_ensure_event_loop_is_singleton(self) -> None:
        loop_a = client._ensure_event_loop()
        loop_b = client._ensure_event_loop()
        self.assertIs(loop_a, loop_b)
        self.assertTrue(loop_a.is_running())

    @patch("vnpy_mcp.remote.client._list_tools_async")
    def test_run_async_uses_persistent_loop(self, list_mock) -> None:
        async def _fake_list(*_args, **_kwargs):
            return []

        list_mock.side_effect = _fake_list
        loop = client._ensure_event_loop()
        client.list_remote_tools("https://example.com/mcp")
        client.list_remote_tools("https://example.com/mcp")
        self.assertTrue(loop.is_running())
        self.assertEqual(list_mock.call_count, 2)


if __name__ == "__main__":
    unittest.main()
