"""申万 2021 行业映射测试。"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

import tests._bootstrap  # noqa: F401
from vnpy_ashare.integrations.tushare.sw_industry import (
    build_grouped_l2_industries,
    format_industry_filter_label,
    member_rows_to_industry_map,
    member_rows_to_l2_parent_map,
    sync_sw_industry_snapshot,
)


class SwIndustryMapTests(unittest.TestCase):
    def test_member_rows_to_l2_map_skips_outdated(self) -> None:
        rows = [
            {"ts_code": "600519.SH", "l2_name": "白酒", "out_date": ""},
            {"ts_code": "000001.SZ", "l2_name": "银行", "out_date": "20240101"},
        ]
        mapping = member_rows_to_industry_map(rows, level="L2")
        self.assertEqual(mapping, {"600519.SH": "白酒"})

    def test_member_rows_l3_fallback(self) -> None:
        rows = [{"ts_code": "000001.SZ", "l3_name": "铜", "l2_name": "工业金属", "out_date": ""}]
        self.assertEqual(member_rows_to_industry_map(rows, level="L3")["000001.SZ"], "铜")
        self.assertEqual(member_rows_to_industry_map(rows, level="L2")["000001.SZ"], "工业金属")

    def test_member_rows_l1_map(self) -> None:
        rows = [
            {"ts_code": "600362.SH", "l1_name": "有色金属", "l2_name": "工业金属", "out_date": ""},
        ]
        self.assertEqual(member_rows_to_industry_map(rows, level="L1")["600362.SH"], "有色金属")

    def test_l2_parent_map(self) -> None:
        rows = [
            {"ts_code": "600362.SH", "l1_name": "有色金属", "l2_name": "工业金属", "out_date": ""},
            {"ts_code": "600519.SH", "l1_name": "食品饮料", "l2_name": "白酒", "out_date": ""},
        ]
        self.assertEqual(member_rows_to_l2_parent_map(rows)["工业金属"], "有色金属")

    def test_build_grouped_l2_industries(self) -> None:
        grouped = build_grouped_l2_industries(
            ["工业金属", "白酒", "银行"],
            {"工业金属": "有色金属", "白酒": "食品饮料"},
        )
        self.assertEqual(grouped[0][0], "有色金属")
        self.assertIn("工业金属", grouped[0][1])
        self.assertEqual(grouped[1][0], "食品饮料")
        self.assertEqual(grouped[1][1], ["白酒"])
        self.assertEqual(grouped[-1], ("", ["银行"]))

    def test_format_industry_filter_label(self) -> None:
        self.assertEqual(format_industry_filter_label("工业金属", "有色金属"), "有色金属 / 工业金属")
        self.assertEqual(format_industry_filter_label("银行"), "银行")

    @patch("vnpy_ashare.integrations.tushare.sw_industry.fetch_sw_member_rows")
    @patch("vnpy_ashare.integrations.tushare.sw_industry.fetch_sw_classify")
    @patch("vnpy_ashare.integrations.tushare.sw_industry.set_cached_l2_to_l1_map")
    @patch("vnpy_ashare.integrations.tushare.sw_industry.set_cached_sw_industry_l1_map")
    @patch("vnpy_ashare.integrations.tushare.sw_industry.set_cached_sw_industry_map")
    @patch("vnpy_ashare.integrations.tushare.sw_industry.set_cached_rows")
    def test_sync_writes_l2_cache(
        self,
        set_rows_mock: MagicMock,
        set_map_mock: MagicMock,
        set_l1_mock: MagicMock,
        set_l2_to_l1_mock: MagicMock,
        classify_mock: MagicMock,
        member_mock: MagicMock,
    ) -> None:
        classify_mock.return_value = [{"industry_name": "有色金属"}]
        member_mock.return_value = [
            {"ts_code": "600362.SH", "l1_name": "有色金属", "l2_name": "工业金属", "out_date": ""},
        ]

        mapping, count = sync_sw_industry_snapshot(force=True)

        self.assertEqual(count, 1)
        self.assertEqual(mapping["600362.SH"], "工业金属")
        set_map_mock.assert_called_once_with({"600362.SH": "工业金属"})
        set_l1_mock.assert_called_once_with({"600362.SH": "有色金属"})
        set_l2_to_l1_mock.assert_called_once_with({"工业金属": "有色金属"})
        set_rows_mock.assert_called()


if __name__ == "__main__":
    unittest.main()
