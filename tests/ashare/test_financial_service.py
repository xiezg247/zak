"""个股财报衍生指标与同步单元测试。"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from vnpy_ashare.services.financial_service import compute_snapshots, sync_symbol_financials
from vnpy_ashare.storage.repositories.financial import list_snapshots, upsert_report


class FinancialDerivedTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        db_path = Path(self._tmpdir.name) / "test.db"

        self._patch_path = patch("vnpy_ashare.storage.connection._db_path", return_value=db_path)
        self._patch_path.start()

        from vnpy_ashare.storage.connection import init_app_db

        init_app_db()

    def tearDown(self) -> None:
        self._patch_path.stop()
        self._tmpdir.cleanup()

    def test_compute_snapshots_yoy(self) -> None:
        ts_code = "600519.SH"
        upsert_report(
            ts_code=ts_code,
            report_type="income",
            end_date="20231231",
            ann_date="20240401",
            period="Annual",
            payload={"total_revenue": 100.0, "n_income_attr_p": 20.0},
        )
        upsert_report(
            ts_code=ts_code,
            report_type="income",
            end_date="20221231",
            ann_date="20230401",
            period="Annual",
            payload={"total_revenue": 80.0, "n_income_attr_p": 10.0},
        )
        upsert_report(
            ts_code=ts_code,
            report_type="fina_indicator",
            end_date="20231231",
            ann_date="20240401",
            period="Annual",
            payload={"roe": 20.0, "grossprofit_margin": 50.0, "debt_to_assets": 30.0},
        )
        upsert_report(
            ts_code=ts_code,
            report_type="fina_indicator",
            end_date="20221231",
            ann_date="20230401",
            period="Annual",
            payload={"roe": 10.0},
        )

        snapshots = compute_snapshots(ts_code)
        self.assertGreaterEqual(len(snapshots), 1)
        latest = snapshots[0]
        self.assertEqual(latest.end_date, "20231231")
        self.assertEqual(latest.revenue_yoy, 25.0)
        self.assertEqual(latest.net_income_yoy, 100.0)
        self.assertEqual(latest.roe_yoy, 100.0)

        stored = list_snapshots(ts_code, limit=2)
        self.assertEqual(stored[0].end_date, "20231231")

    @patch("vnpy_ashare.services.financial_service.fetch_all_financial_reports")
    def test_sync_symbol_skips_when_fresh(self, mock_fetch) -> None:
        mock_fetch.return_value = {
            "income": [
                {
                    "end_date": "20231231",
                    "ann_date": "20240401",
                    "period": "Annual",
                    "fields": {"total_revenue": 1.0},
                }
            ],
            "balancesheet": [],
            "cashflow": [],
            "fina_indicator": [],
        }
        first = sync_symbol_financials("600519.SSE", force=True)
        self.assertTrue(first.synced)
        second = sync_symbol_financials("600519.SSE", force=False)
        self.assertTrue(second.skipped)
        self.assertEqual(mock_fetch.call_count, 1)


if __name__ == "__main__":
    unittest.main()
