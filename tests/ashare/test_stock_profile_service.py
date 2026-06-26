"""板块、估值与披露计划单元测试。"""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

from tests.ashare.pg_unittest import PgAppStorageTestCase
from vnpy_ashare.services.financial import sync_symbol_financials
from vnpy_ashare.services.stock.profile import build_valuation_profile
from vnpy_ashare.storage.repositories.disclosure import upsert_disclosure_rows
from vnpy_ashare.storage.repositories.valuation import upsert_valuation_rows


class StockProfileServiceTests(PgAppStorageTestCase):

    def test_valuation_percentile(self) -> None:
        ts_code = "600519.SH"
        rows = [{"trade_date": f"2024010{i}", "pe_ttm": float(i), "pb": float(i) / 10} for i in range(1, 6)]
        upsert_valuation_rows(ts_code, rows)

        with patch(
            "vnpy_ashare.services.stock.profile.fetch_daily_basic_with_fallback",
            return_value=([], ""),
        ):
            profile = build_valuation_profile("600519.SSE")

        self.assertEqual(profile.pe_ttm, 5.0)
        self.assertEqual(profile.pe_percentile_3y, 100.0)
        self.assertEqual(profile.pb_percentile_3y, 100.0)

    @patch("vnpy_ashare.services.financial.fetch_all_financial_reports")
    def test_disclosure_triggers_resync(self, mock_fetch) -> None:
        ts_code = "600519.SH"
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
        sync_symbol_financials("600519.SSE", force=True)
        future_ann = (datetime.now() + timedelta(days=1)).strftime("%Y%m%d")
        upsert_disclosure_rows(
            ts_code,
            [{"end_date": "20240331", "pre_date": "20240428", "ann_date": future_ann}],
        )
        second = sync_symbol_financials("600519.SSE", force=False)
        self.assertFalse(second.skipped)
        self.assertEqual(mock_fetch.call_count, 2)


if __name__ == "__main__":
    unittest.main()
