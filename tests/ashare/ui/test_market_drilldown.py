"""market_drilldown 单元测试。"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from vnpy_ashare.ui.quotes.page.market_drilldown import (
    apply_pending_market_drilldown,
    clear_market_drilldown_filters,
    set_market_industry_filter,
)


class MarketDrilldownTests(unittest.TestCase):
    def setUp(self) -> None:
        self.page = MagicMock()
        self.page._market_industry_filter_listener = MagicMock()
        self.page._table = MagicMock()

    def test_apply_pending_returns_false_when_empty(self) -> None:
        self.page._pending_concept_drilldown = None
        self.page._pending_industry_drilldown = None

        self.assertFalse(apply_pending_market_drilldown(self.page))

    def test_apply_pending_industry(self) -> None:
        self.page._pending_concept_drilldown = None
        self.page._pending_industry_drilldown = "银行"

        self.assertTrue(apply_pending_market_drilldown(self.page))

        self.assertEqual(self.page._market_industry_filter, "银行")
        self.page._market_industry_filter_listener.assert_called_once_with("银行")

    def test_set_market_industry_filter_clears_whitelist(self) -> None:
        set_market_industry_filter(self.page, "医药")

        self.assertEqual(self.page._market_industry_filter, "医药")
        self.assertIsNone(self.page._market_vt_whitelist)
        self.page._table.filter_market_display.assert_called_once()

    def test_clear_market_drilldown_filters(self) -> None:
        clear_market_drilldown_filters(self.page)

        self.assertIsNone(self.page._market_industry_filter)
        self.assertIsNone(self.page._market_vt_whitelist)
        self.page._market_industry_filter_listener.assert_called_once_with(None)


if __name__ == "__main__":
    unittest.main()
