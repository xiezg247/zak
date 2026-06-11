"""字体选择与平台候选测试。"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from vnpy_ashare.config import fonts


class FontSelectionTest(unittest.TestCase):
    @patch("vnpy_ashare.config.fonts.platform.system", return_value="Darwin")
    def test_font_family_candidates_macos(self, _system: object) -> None:
        self.assertEqual(fonts.font_family_candidates(), fonts.MACOS_FONTS)

    @patch("vnpy_ashare.config.fonts.platform.system", return_value="Windows")
    def test_font_family_candidates_windows(self, _system: object) -> None:
        self.assertEqual(fonts.font_family_candidates(), fonts.WINDOWS_FONTS)

    @patch("vnpy_ashare.config.fonts.available_font_families", return_value=("PingFang SC", "Arial"))
    def test_supports_font_family_selection_when_multiple(
        self,
        _available: object,
    ) -> None:
        self.assertTrue(fonts.supports_font_family_selection())

    @patch("vnpy_ashare.config.fonts.available_font_families", return_value=("PingFang SC",))
    def test_supports_font_family_selection_when_single(
        self,
        _available: object,
    ) -> None:
        self.assertFalse(fonts.supports_font_family_selection())

    @patch("vnpy_ashare.config.fonts.platform.system", return_value="Darwin")
    def test_resolve_font_family_rejects_unavailable_on_macos(self, _system: object) -> None:
        self.assertEqual(fonts.resolve_font_family("微软雅黑"), fonts.MACOS_FONTS[0])
