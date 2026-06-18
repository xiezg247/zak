"""AI 助手设置 Tab 测试。"""

from __future__ import annotations

import unittest

from vnpy.trader.ui import QtWidgets

from vnpy_ashare.ui.shell.settings.ai_section import AiSettingsSection
from vnpy_ashare.ui.shell.settings.dialog import SettingsDialog
from vnpy_llm.config.nl_screening_prefs import (
    load_nl_screening_confirm_enabled,
    save_nl_screening_confirm_enabled,
)


class AiSettingsSectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def test_ai_settings_section_save_nl_screening_confirm(self) -> None:
        dialog = SettingsDialog()
        section = dialog._ai_section
        self.assertIsInstance(section, AiSettingsSection)

        save_nl_screening_confirm_enabled(True)
        section.refresh()
        self.assertTrue(section._nl_screening_confirm.isChecked())

        section._nl_screening_confirm.setChecked(False)
        self.assertTrue(section.save_prefs())
        self.assertFalse(load_nl_screening_confirm_enabled())

        section._nl_screening_confirm.setChecked(False)
        self.assertFalse(section.save_prefs())

        save_nl_screening_confirm_enabled(True)
