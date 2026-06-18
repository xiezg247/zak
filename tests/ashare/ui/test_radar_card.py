"""雷达卡片布局单元测试。"""

from __future__ import annotations

import unittest

import tests._bootstrap  # noqa: F401
from vnpy.trader.ui import QtWidgets

from vnpy_ashare.domain.radar.card import RadarCardData, RadarRow
from vnpy_ashare.quotes.radar.radar_catalog import RADAR_CARD_BY_ID
from vnpy_ashare.ui.quotes.radar.card import RadarCardWidget, _BODY_PAGE_EMPTY, _BODY_PAGE_ROWS


class RadarCardWidgetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def _card(self) -> RadarCardWidget:
        spec = RADAR_CARD_BY_ID["sector_theme"]
        return RadarCardWidget(spec)

    def test_empty_state_uses_body_stack_and_keeps_header_visible(self) -> None:
        card = self._card()
        card.resize(360, 480)
        card.show()
        QtWidgets.QApplication.processEvents()

        card.apply_data(
            RadarCardData(
                card_id="sector_theme",
                title="板块·主线",
                subtitle="概念数据未就绪",
                rows=(),
                empty_message="暂无概念板块数据，请先运行 Tushare 概念预拉取任务。",
                updated_at="",
            ),
        )
        QtWidgets.QApplication.processEvents()

        self.assertEqual(card._body_stack.currentIndex(), _BODY_PAGE_EMPTY)
        self.assertTrue(card._title.isVisible())
        self.assertGreater(card._body_stack.height(), card._title.height())

    def test_rows_state_uses_scroll_page(self) -> None:
        card = self._card()
        card.apply_data(
            RadarCardData(
                card_id="sector_theme",
                title="板块·主线",
                subtitle="",
                rows=(
                    RadarRow(
                        vt_symbol="000001.SZSE",
                        name="平安银行",
                        symbol="000001",
                        price=10.5,
                        change_pct=1.2,
                        metric_label="涨幅",
                        metric_value="+1.2%",
                        sub_label="",
                        sub_value="",
                    ),
                ),
                empty_message="",
                updated_at="12:00",
            ),
        )

        self.assertEqual(card._body_stack.currentIndex(), _BODY_PAGE_ROWS)
        self.assertEqual(len(card._row_widgets), 1)


if __name__ == "__main__":
    unittest.main()
