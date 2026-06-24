"""Markdown 渲染字体栈测试。"""

from __future__ import annotations

from unittest.mock import patch

from vnpy_llm.ui.panel import md_renderer


def test_monospace_font_stack_macos_uses_system_fonts() -> None:
    with patch.object(md_renderer.platform, "system", return_value="Darwin"):
        stack = md_renderer._monospace_font_stack()
    assert "Menlo" in stack
    assert "monospace" not in stack
    assert "JetBrains Mono" not in stack


def test_monospace_font_stack_windows() -> None:
    with patch.object(md_renderer.platform, "system", return_value="Windows"):
        stack = md_renderer._monospace_font_stack()
    assert "Consolas" in stack
