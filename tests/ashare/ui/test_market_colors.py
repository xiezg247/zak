"""行情涨跌语义色测试。"""

from __future__ import annotations

import unittest

from vnpy_common.ui.theme.market_colors import market_colors, quote_change_color
from vnpy_common.ui.theme.tokens import DARK_TOKENS, LIGHT_TOKENS


class _QuoteStub:
    def __init__(self, *, is_rise: bool = False, is_fall: bool = False) -> None:
        self.is_rise = is_rise
        self.is_fall = is_fall


class MarketColorsTests(unittest.TestCase):
    def test_light_theme_uses_darker_green_than_dark(self) -> None:
        dark = market_colors(DARK_TOKENS)
        light = market_colors(LIGHT_TOKENS)
        self.assertEqual(dark.rise, "#ff4d4f")
        self.assertEqual(light.fall, "#15803d")
        self.assertNotEqual(dark.fall, light.fall)

    def test_quote_change_color_follows_tokens(self) -> None:
        rise = quote_change_color(_QuoteStub(is_rise=True), LIGHT_TOKENS)
        fall = quote_change_color(_QuoteStub(is_fall=True), LIGHT_TOKENS)
        flat = quote_change_color(_QuoteStub(), LIGHT_TOKENS)
        self.assertEqual(rise, LIGHT_TOKENS.market_rise)
        self.assertEqual(fall, LIGHT_TOKENS.market_fall)
        self.assertEqual(flat, LIGHT_TOKENS.market_flat)


if __name__ == "__main__":
    unittest.main()
