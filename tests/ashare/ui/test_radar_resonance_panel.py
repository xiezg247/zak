"""雷达共振侧栏折叠单元测试。"""

from __future__ import annotations

import unittest

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.ui.quotes.radar.resonance_panel import (
    RESONANCE_COLLAPSED_WIDTH,
    RESONANCE_HANDLE_WIDTH,
    RadarResonancePanel,
    resonance_collapse_arrow,
)
from vnpy_ashare.ui.quotes.radar.section_prefs import (
    load_radar_resonance_expanded,
    save_radar_resonance_expanded,
)


class RadarResonanceSettingsTests(unittest.TestCase):
    def test_expanded_settings_roundtrip(self) -> None:
        save_radar_resonance_expanded(False)
        self.assertFalse(load_radar_resonance_expanded())
        save_radar_resonance_expanded(True)
        self.assertTrue(load_radar_resonance_expanded())


class RadarResonancePanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def test_collapse_hides_body_and_narrows_panel(self) -> None:
        save_radar_resonance_expanded(True)
        panel = RadarResonancePanel()
        panel.resize(320, 600)
        panel.show()
        QtWidgets.QApplication.processEvents()

        panel.set_expanded(False)
        QtWidgets.QApplication.processEvents()

        self.assertFalse(panel._body.isVisible())
        self.assertLessEqual(panel.width(), RESONANCE_COLLAPSED_WIDTH + 2)
        self.assertGreaterEqual(panel.width(), RESONANCE_HANDLE_WIDTH)

        panel.set_expanded(True)
        QtWidgets.QApplication.processEvents()
        self.assertTrue(panel._body.isVisible())

    def test_collapse_arrow_uses_horizontal_chevrons(self) -> None:
        self.assertEqual(
            resonance_collapse_arrow(True),
            QtCore.Qt.ArrowType.LeftArrow,
        )
        self.assertEqual(
            resonance_collapse_arrow(False),
            QtCore.Qt.ArrowType.RightArrow,
        )


if __name__ == "__main__":
    unittest.main()
