"""行业映射合并（申万 L2 + stock_basic 回退）。"""

from __future__ import annotations

import unittest

import tests._bootstrap  # noqa: F401
from vnpy_ashare.integrations.tushare.cache import merge_industry_maps
from vnpy_ashare.integrations.tushare.factors import fetch_stock_industry_map


class IndustryMapMergeTests(unittest.TestCase):
    def test_merge_industry_maps_sw_overrides_basic(self) -> None:
        merged = merge_industry_maps(
            {"600519.SH": "白酒"},
            {"600519.SH": "旧行业", "000001.SZ": "银行"},
        )
        self.assertEqual(merged["600519.SH"], "白酒")
        self.assertEqual(merged["000001.SZ"], "银行")

    def test_fetch_stock_industry_map_fills_gaps_from_basic(self) -> None:
        from unittest.mock import patch

        with (
            patch(
                "vnpy_ashare.integrations.tushare.factors.get_cached_sw_industry_map",
                return_value={"600519.SH": "白酒"},
            ),
            patch(
                "vnpy_ashare.integrations.tushare.factors.get_cached_stock_basic_industry_map",
                return_value={"600519.SH": "旧行业", "000001.SZ": "银行"},
            ),
        ):
            mapping = fetch_stock_industry_map()
        self.assertEqual(mapping["600519.SH"], "白酒")
        self.assertEqual(mapping["000001.SZ"], "银行")


if __name__ == "__main__":
    unittest.main()
