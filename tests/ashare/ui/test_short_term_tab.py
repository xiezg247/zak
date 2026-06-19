"""短线 Tab 布局测试。"""

from __future__ import annotations

import unittest

from vnpy.trader.ui import QtWidgets

import tests._bootstrap  # noqa: F401
from vnpy_ashare.domain.stock.short_term import ShortTermProfile
from vnpy_ashare.ui.features.stock_analysis.short_term_tab import ShortTermAnalysisTab, _fit_table_height


class ShortTermTabLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def test_non_limit_up_hides_limit_card(self) -> None:
        tab = ShortTermAnalysisTab()
        tab.show()
        tab.show_profile(
            ShortTermProfile(
                ts_code="688300.SH",
                vt_symbol="688300.SSE",
                name="联瑞新材",
                leader_tier_label="龙一",
                sector_name="非金属材料II",
                sector_rank=1,
                entry_mode={
                    "recommended_label": "半路",
                    "emotion_stage_label": "发酵/高潮",
                    "allow_new_positions": True,
                    "scores": [{"label": "半路", "score": 65.0, "reasons": ["趋势尚可"]}],
                },
                message="今日未在涨停列表",
            ),
        )
        QtWidgets.QApplication.processEvents()
        self.assertFalse(tab._limit_card.isVisible())
        self.assertTrue(tab._limit_idle_hint.isVisible())

    def test_fit_table_height_uses_row_count(self) -> None:
        table = QtWidgets.QTableWidget(5, 2)
        _fit_table_height(table, min_rows=2, max_rows=8)
        expected = 28 + 5 * 30 + 4
        self.assertEqual(table.minimumHeight(), expected)
        self.assertEqual(table.maximumHeight(), expected)


if __name__ == "__main__":
    unittest.main()
