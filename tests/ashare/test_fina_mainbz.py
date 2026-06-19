"""主营业务构成（fina_mainbz）聚合单元测试。"""

from __future__ import annotations

import unittest

from vnpy_ashare.integrations.tushare.financial import _group_mainbz_rows


class FinaMainbzTests(unittest.TestCase):
    def test_group_mainbz_rows_by_period(self) -> None:
        rows = _group_mainbz_rows(
            [
                {
                    "end_date": "20231231",
                    "bz_item": "茅台酒",
                    "bz_sales": 100.0,
                    "bz_profit": 60.0,
                    "bz_cost": 40.0,
                    "bz_code": "P",
                },
                {
                    "end_date": "20231231",
                    "bz_item": "系列酒",
                    "bz_sales": 20.0,
                    "bz_profit": None,
                    "bz_cost": None,
                    "bz_code": "P",
                },
                {
                    "end_date": "20221231",
                    "bz_item": "茅台酒",
                    "bz_sales": 80.0,
                    "bz_profit": 50.0,
                    "bz_cost": 30.0,
                    "bz_code": "P",
                },
            ]
        )
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["end_date"], "20231231")
        self.assertEqual(rows[0]["period"], "Annual")
        items = rows[0]["fields"]["items"]
        self.assertEqual(items[0]["bz_item"], "茅台酒")
        self.assertEqual(items[0]["bz_sales"], 100.0)
        self.assertIsNone(items[1]["bz_profit"])


if __name__ == "__main__":
    unittest.main()
