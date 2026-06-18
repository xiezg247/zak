"""SymbolNavigation 桥接注册。"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from vnpy_ashare.ai.ui.symbol_navigation import build_ashare_symbol_navigation
from vnpy_ashare.app.bootstrap import install_shared_bridges
from vnpy_common.ai.protocol import AiContextData
from vnpy_common.ai.symbol_navigation import get_symbol_navigation


class SymbolNavigationBridgeTests(unittest.TestCase):
    def test_bootstrap_registers_navigation(self) -> None:
        install_shared_bridges()
        nav = get_symbol_navigation()
        self.assertIsNotNone(nav)

    def test_parse_normalizes_suffix(self) -> None:
        install_shared_bridges()
        nav = get_symbol_navigation()
        assert nav is not None
        ref = nav.parse("600519.SH")
        self.assertIsNotNone(ref)
        assert ref is not None
        self.assertEqual(ref.vt_symbol, "600519.SSE")

    def test_resolve_context_symbol(self) -> None:
        install_shared_bridges()
        nav = get_symbol_navigation()
        assert nav is not None
        ref = nav.resolve_context_symbol()
        self.assertIsNone(ref)

    def test_resolve_context_symbol_cn_exchange(self) -> None:
        install_shared_bridges()
        nav = get_symbol_navigation()
        assert nav is not None
        with patch(
            "vnpy_ashare.ai.ui.symbol_navigation.get_ai_context",
            return_value=AiContextData(page="自选", symbol="600519", exchange="上交所", name="茅台"),
        ):
            ref = nav.resolve_context_symbol()
        self.assertIsNotNone(ref)
        assert ref is not None
        self.assertEqual(ref.vt_symbol, "600519.SSE")

    def test_normalize_vt_symbol(self) -> None:
        install_shared_bridges()
        nav = get_symbol_navigation()
        assert nav is not None
        self.assertEqual(nav.normalize_vt_symbol("600519"), "600519.SSE")

    def test_build_returns_port(self) -> None:
        port = build_ashare_symbol_navigation()
        self.assertTrue(hasattr(port, "open_analysis"))


if __name__ == "__main__":
    unittest.main()
