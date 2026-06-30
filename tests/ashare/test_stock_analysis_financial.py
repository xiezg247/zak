"""个股分析财务 Tab 加载逻辑单元测试。"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from vnpy_ashare.domain.financial.bundle import FinancialBundle, FinancialSyncResult
from vnpy_ashare.services.financial import bundle_has_local_data
from vnpy_ashare.services.stock_analysis import StockAnalysisPayload, StockAnalysisService


class _FakeFinancialService:
    def __init__(self) -> None:
        self.get_or_sync_calls = 0
        self.get_bundle_calls = 0

    def get_bundle(self, vt_symbol: str, *, periods: int = 12) -> FinancialBundle:
        self.get_bundle_calls += 1
        return FinancialBundle(
            ts_code="600519.SH",
            vt_symbol=vt_symbol,
            name="贵州茅台",
            sync_meta=None,
            snapshots=[],
            reports={},
        )

    def get_or_sync(self, vt_symbol: str, **kwargs) -> tuple[FinancialBundle, FinancialSyncResult]:
        self.get_or_sync_calls += 1
        bundle = FinancialBundle(
            ts_code="600519.SH",
            vt_symbol=vt_symbol,
            name="贵州茅台",
            sync_meta=None,
            snapshots=[],
            reports={"income": [{"end_date": "20231231", "fields": {"total_revenue": 100.0}}]},
        )
        result = FinancialSyncResult(
            ts_code="600519.SH",
            vt_symbol=vt_symbol,
            synced=True,
            message="已同步",
        )
        return bundle, result


class StockAnalysisFinancialLoadTests(unittest.TestCase):
    def test_bundle_has_local_data_empty(self) -> None:
        bundle = FinancialBundle(
            ts_code="600519.SH",
            vt_symbol="600519.SSE",
            name="贵州茅台",
            sync_meta=None,
            snapshots=[],
            reports={},
        )
        self.assertFalse(bundle_has_local_data(bundle))
        self.assertFalse(bundle_has_local_data(None))

    def test_bundle_has_local_data_with_reports(self) -> None:
        bundle = FinancialBundle(
            ts_code="600519.SH",
            vt_symbol="600519.SSE",
            name="贵州茅台",
            sync_meta=None,
            snapshots=[],
            reports={"income": [{"end_date": "20231231", "fields": {}}]},
        )
        self.assertTrue(bundle_has_local_data(bundle))

    @patch("vnpy_ashare.services.stock_analysis.build_overview_dashboard")
    @patch("vnpy_ashare.services.stock_analysis.load_daily_bars_tail", return_value=[])
    @patch("vnpy_ashare.services.stock_analysis.compute_relative_returns", return_value={})
    def test_load_financial_auto_syncs_when_local_empty(
        self,
        _mock_relative: MagicMock,
        _mock_bars: MagicMock,
        _mock_dashboard: MagicMock,
    ) -> None:
        engine = MagicMock()
        fake_financial = _FakeFinancialService()
        engine.financial_service = fake_financial
        engine.analysis_service.technical_snapshot.return_value = {}

        service = StockAnalysisService(engine)
        payload = service.load_scope("600519.SSE", "financial", sync_financials=False)

        self.assertEqual(fake_financial.get_bundle_calls, 1)
        self.assertEqual(fake_financial.get_or_sync_calls, 1)
        self.assertIsNotNone(payload.financial_bundle)
        self.assertTrue(payload.financial_bundle.reports.get("income"))
        self.assertIsNotNone(payload.financial_sync)
        self.assertEqual(payload.financial_sync.message, "已同步")


if __name__ == "__main__":
    unittest.main()
