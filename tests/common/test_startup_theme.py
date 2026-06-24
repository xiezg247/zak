"""启动与主题缓存相关单元测试。"""

from __future__ import annotations

from vnpy_common.ui.theme.build import build_terminal_stylesheet, cached_terminal_stylesheet
from vnpy_common.ui.theme.tokens import get_tokens


def test_cached_terminal_stylesheet_matches_build() -> None:
    for theme_id in ("dark", "light"):
        tokens = get_tokens(theme_id)
        assert cached_terminal_stylesheet(theme_id) == build_terminal_stylesheet(tokens)
        # 二次调用应命中缓存（同一对象）
        assert cached_terminal_stylesheet(theme_id) is cached_terminal_stylesheet(theme_id)
