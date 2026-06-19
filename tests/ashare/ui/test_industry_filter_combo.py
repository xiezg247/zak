"""市场页行业筛选解析。"""

from __future__ import annotations

import unittest

from vnpy_ashare.ui.quotes.market_overview.industry_filter_combo import resolve_industry_name


class ResolveIndustryNameTests(unittest.TestCase):
    def setUp(self) -> None:
        self.industries = frozenset({"银行", "半导体", "元件", "半导体设备"})

    def test_empty_returns_none(self) -> None:
        self.assertIsNone(resolve_industry_name("", self.industries))
        self.assertIsNone(resolve_industry_name("  ", self.industries))

    def test_exact_match(self) -> None:
        self.assertEqual(resolve_industry_name("银行", self.industries), "银行")

    def test_unique_contains_match(self) -> None:
        self.assertEqual(resolve_industry_name("银", frozenset({"银行"})), "银行")

    def test_ambiguous_returns_none(self) -> None:
        self.assertIsNone(resolve_industry_name("半导", self.industries))
        self.assertIsNone(resolve_industry_name("体", self.industries))

    def test_exact_beats_partial(self) -> None:
        self.assertEqual(resolve_industry_name("半导体", self.industries), "半导体")

    def test_unknown_returns_none(self) -> None:
        self.assertIsNone(resolve_industry_name("不存在", self.industries))

    def test_grouped_label_resolves_l2(self) -> None:
        self.assertEqual(resolve_industry_name("食品饮料 / 白酒", frozenset({"白酒"})), "白酒")
        self.assertEqual(resolve_industry_name("有色金属 / 工业金属", frozenset({"工业金属"})), "工业金属")


if __name__ == "__main__":
    unittest.main()
