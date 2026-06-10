"""主题切换单元测试。"""

from __future__ import annotations

import unittest

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.paths import QSETTINGS_ORG
from vnpy_ashare.ui.theme import (
    ThemeManager,
    build_ai_panel_stylesheet,
    build_chart_panel_stylesheet,
    build_settings_stylesheet,
    get_tokens,
    stylesheet_for,
    theme_manager,
)
from vnpy_ashare.ui.theme.tokens import DARK_TOKENS, LIGHT_TOKENS


class ThemeManagerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def setUp(self) -> None:
        ThemeManager._instance = None
        settings = QtCore.QSettings(QSETTINGS_ORG, "ashare_ui")
        settings.remove("ui_theme")

    def test_stylesheets_differ_between_dark_and_light(self) -> None:
        dark = stylesheet_for("dark")
        light = stylesheet_for("light")
        self.assertIn(DARK_TOKENS.app_bg, dark)
        self.assertIn(LIGHT_TOKENS.app_bg, light)
        self.assertNotEqual(dark, light)

    def test_extra_builders_follow_theme(self) -> None:
        dark_settings = build_settings_stylesheet(DARK_TOKENS)
        light_settings = build_settings_stylesheet(LIGHT_TOKENS)
        self.assertIn(DARK_TOKENS.app_bg, dark_settings)
        self.assertIn(LIGHT_TOKENS.app_bg, light_settings)

        dark_chart = build_chart_panel_stylesheet(DARK_TOKENS)
        light_chart = build_chart_panel_stylesheet(LIGHT_TOKENS)
        self.assertNotEqual(dark_chart, light_chart)

        dark_ai = build_ai_panel_stylesheet(DARK_TOKENS)
        light_ai = build_ai_panel_stylesheet(LIGHT_TOKENS)
        self.assertNotEqual(dark_ai, light_ai)

    def test_scheduler_log_html_uses_semantic_colors(self) -> None:
        from vnpy_ashare.scheduler import JobRunRecord
        from vnpy_ashare.ui.theme.build_extra import format_scheduler_run_log_html

        record = JobRunRecord(
            job_id="test",
            job_name="行情采集",
            finished_at="2026-01-01 09:00:00",
            success=True,
            skipped=False,
            message="ok",
        )
        html = format_scheduler_run_log_html(LIGHT_TOKENS, [record])
        self.assertIn(LIGHT_TOKENS.semantic_success, html)
        self.assertIn(LIGHT_TOKENS.text_primary, html)

    def test_orb_palette_follows_accent(self) -> None:
        from vnpy_ashare.ui.theme.orb_palette import orb_palette

        dark_orb = orb_palette(DARK_TOKENS)
        light_orb = orb_palette(LIGHT_TOKENS)
        self.assertNotEqual(dark_orb.idle_gradient, light_orb.idle_gradient)

    def test_html_palette_and_diagnose_html(self) -> None:
        from vnpy_ashare.ui.diagnose_panel import format_diagnose_html
        from vnpy_ashare.ui.theme.html_palette import html_palette

        palette = html_palette(LIGHT_TOKENS)
        self.assertEqual(palette.section, LIGHT_TOKENS.accent)
        html = format_diagnose_html({"error": "测试错误"}, tokens=LIGHT_TOKENS)
        self.assertIn(LIGHT_TOKENS.semantic_error, html)

    def test_set_theme_persists_and_applies(self) -> None:
        manager = theme_manager()
        manager.load_saved()
        self.assertEqual(manager.current(), "dark")

        panel = QtWidgets.QWidget()
        manager.bind_stylesheet(panel, extra=build_settings_stylesheet)
        manager.set_theme("light")
        self.assertEqual(manager.current(), "light")
        self.assertIn(LIGHT_TOKENS.app_bg, panel.styleSheet())

        manager.set_theme("dark")
        saved = QtCore.QSettings(QSETTINGS_ORG, "ashare_ui")
        self.assertEqual(saved.value("ui_theme"), "dark")

    def test_get_tokens_returns_expected_palette(self) -> None:
        self.assertEqual(get_tokens("dark").accent, DARK_TOKENS.accent)
        self.assertEqual(get_tokens("light").nav_bg, LIGHT_TOKENS.nav_bg)


if __name__ == "__main__":
    unittest.main()
