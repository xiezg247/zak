"""系统主题检测测试。"""

from __future__ import annotations

import unittest

from vnpy.trader.ui import QtWidgets

from vnpy_common.ui.theme.system import detect_system_theme_id, resolve_theme_id


class SystemThemeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def test_resolve_theme_id_honors_dark_preference(self) -> None:
        self.assertEqual(resolve_theme_id("dark"), "dark")

    def test_resolve_system_delegates_to_detector(self) -> None:
        self.assertEqual(resolve_theme_id("system"), detect_system_theme_id())

    def test_detect_system_theme_id_returns_dark_or_light(self) -> None:
        self.assertIn(detect_system_theme_id(), ("dark", "light"))


if __name__ == "__main__":
    unittest.main()
