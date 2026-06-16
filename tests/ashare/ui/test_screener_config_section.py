"""选股左栏折叠分组测试。"""

from __future__ import annotations

import unittest

from vnpy.trader.ui import QtWidgets

from vnpy_ashare.ui.screener.widgets.screener_config_section import (
    ScreenerConfigSection,
    load_config_section_expanded,
    save_config_section_expanded,
)


class ScreenerConfigSectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def test_section_collapses_content(self) -> None:
        section = ScreenerConfigSection(
            "基础条件",
            section_id="test_basic",
            expanded=True,
            persist=False,
        )
        section.show()
        label = QtWidgets.QLabel("child")
        section.content_layout().addWidget(label)

        content = section.findChild(QtWidgets.QWidget, "ScreenerConfigSectionContent")
        self.assertIsNotNone(content)
        self.assertTrue(section.is_expanded())
        self.assertTrue(content.isVisible())

        section.collapse()
        self.assertFalse(section.is_expanded())
        self.assertFalse(content.isVisible())

    def test_section_persistence_roundtrip(self) -> None:
        section_id = "test_persist_roundtrip"
        save_config_section_expanded(section_id, False)
        self.assertFalse(load_config_section_expanded(section_id, True))
        save_config_section_expanded(section_id, True)
        self.assertTrue(load_config_section_expanded(section_id, False))


if __name__ == "__main__":
    unittest.main()
