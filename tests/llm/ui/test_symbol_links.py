"""AI 助手标的链接单元测试。"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from vnpy_llm.ui.panel.symbol_links import linkify_markdown, normalize_vt_symbol, parse_symbol_href, symbol_href


class SymbolLinksTests(unittest.TestCase):
    def test_linkify_vt_symbol(self) -> None:
        text = "建议关注 600519.SSE 与 000001.SZSE。"
        linked = linkify_markdown(text)
        self.assertIn(symbol_href("600519.SSE"), linked)
        self.assertIn(symbol_href("000001.SZSE"), linked)

    def test_linkify_bare_code(self) -> None:
        linked = linkify_markdown("候选：600519、000858。")
        self.assertIn("600519", linked)
        self.assertIn("zak://symbol/", linked)

    def test_skip_fenced_code(self) -> None:
        text = "```python\nvt = '600519.SSE'\n```\n正文 600519.SSE"
        linked = linkify_markdown(text)
        self.assertNotIn("zak://symbol/", linked.split("```")[1])
        self.assertIn("zak://symbol/", linked)

    def test_parse_symbol_href(self) -> None:
        href = symbol_href("600519.SSE")
        self.assertEqual(parse_symbol_href(href), "600519.SSE")
        self.assertIsNone(parse_symbol_href("https://example.com"))

    def test_normalize_tickflow_suffix(self) -> None:
        self.assertEqual(normalize_vt_symbol("600519.SH"), "600519.SSE")

    def test_normalize_bare_code_fallback_without_nav(self) -> None:
        with patch("vnpy_common.ai.symbol_navigation.get_symbol_navigation", return_value=None):
            self.assertEqual(normalize_vt_symbol("600519"), "600519.SSE")
            self.assertEqual(normalize_vt_symbol("300750"), "300750.SZSE")


if __name__ == "__main__":
    unittest.main()
