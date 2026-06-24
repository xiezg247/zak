"""等宽字体工具测试。"""

from __future__ import annotations

from unittest.mock import patch

from vnpy_common.ui.monospace_font import monospace_font_css_stack


def test_monospace_font_css_stack_excludes_generic_monospace() -> None:
    with patch("vnpy_common.ui.monospace_font.platform.system", return_value="Darwin"):
        stack = monospace_font_css_stack()
    assert "monospace" not in stack.lower().split(", ")
    assert "Menlo" in stack


def test_monospace_font_css_stack_quoted_for_html() -> None:
    with patch("vnpy_common.ui.monospace_font.platform.system", return_value="Darwin"):
        stack = monospace_font_css_stack(quoted=True)
    assert stack.startswith('"Menlo"')
    assert "monospace" not in stack
