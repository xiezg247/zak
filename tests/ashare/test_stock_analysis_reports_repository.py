"""个股分析报告 repository 测试。"""

from __future__ import annotations

import json
import unittest

from vnpy.trader.constant import Exchange

from tests.ashare.pg_unittest import PgStorageTestCase
from vnpy_ashare.storage.repositories import stock_analysis_reports as repo


class StockAnalysisReportsRepositoryTests(PgStorageTestCase):

    def test_create_list_and_delete_report(self) -> None:
        context = json.dumps({"scope": "overview", "summary": "PE 分位 20%"}, ensure_ascii=False)
        created = repo.create_report(
            "600519",
            Exchange.SSE,
            title="茅台 · 概览",
            body="# 结论\n\n估值合理。",
            source_scope="overview",
            context_json=context,
        )
        self.assertGreater(int(created["id"]), 0)
        rows = repo.list_reports("600519", Exchange.SSE)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["title"], "茅台 · 概览")
        loaded = repo.get_report(int(created["id"]))
        self.assertIsNotNone(loaded)
        assert loaded is not None
        self.assertIn("估值合理", loaded["body"])
        self.assertTrue(repo.delete_report(int(created["id"])))
        self.assertEqual(repo.list_reports("600519", Exchange.SSE), [])

    def test_create_empty_body_rejected(self) -> None:
        with self.assertRaises(ValueError):
            repo.create_report("600519", Exchange.SSE, title="空", body="  ")


if __name__ == "__main__":
    unittest.main()
