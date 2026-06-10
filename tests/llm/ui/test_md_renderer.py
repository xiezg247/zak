"""Markdown 渲染主题测试。"""

from __future__ import annotations

import unittest

from vnpy_common.ui.theme.tokens import DARK_TOKENS, LIGHT_TOKENS
from vnpy_llm.ui.md_renderer import render_markdown


class MarkdownRendererThemeTests(unittest.TestCase):
    def test_light_theme_uses_dark_text_and_light_table(self) -> None:
        html = render_markdown("| a | b |\n|---|---|\n| 1 | 2 |", tokens=LIGHT_TOKENS)
        self.assertIn(LIGHT_TOKENS.text_primary, html)
        self.assertIn(LIGHT_TOKENS.table_bg, html)
        self.assertNotIn("#e0e0e0", html)
        self.assertNotIn("#0d1117", html)

    def test_dark_theme_keeps_dark_codeblock_background(self) -> None:
        html = render_markdown("```py\nx = 1\n```", tokens=DARK_TOKENS)
        self.assertIn(DARK_TOKENS.text_primary, html)
        self.assertIn("#0d1117", html)


if __name__ == "__main__":
    unittest.main()
