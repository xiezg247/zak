"""概览仪表盘单元测试。"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from vnpy_ashare.ai.context.store import set_screening_results
from vnpy_ashare.services.stock.overview_dashboard import (
    build_overview_dashboard,
    find_screening_hit,
)


class OverviewDashboardTests(unittest.TestCase):
    def tearDown(self) -> None:
        set_screening_results(condition="", rows=[], updated_at=None)

    def test_find_screening_hit(self) -> None:
        set_screening_results(
            condition="双均线金叉",
            rows=[
                {"vt_symbol": "600000.SSE", "name": "浦发银行"},
                {"vt_symbol": "600519.SSE", "name": "贵州茅台"},
            ],
            updated_at="2024-06-01",
        )
        hit = find_screening_hit("600519.SSE")
        self.assertIsNotNone(hit)
        assert hit is not None
        self.assertEqual(hit.rank, 2)
        self.assertEqual(hit.condition, "双均线金叉")

    @patch("vnpy_ashare.services.stock.overview_dashboard.build_moneyflow_profile")
    @patch("vnpy_ashare.services.stock.overview_dashboard.build_valuation_profile")
    @patch("vnpy_ashare.services.stock.overview_dashboard.list_valuation_history")
    @patch("vnpy_ashare.services.stock.overview_dashboard._tushare_configured", return_value=False)
    def test_build_overview_dashboard_readiness(
        self,
        _tushare_ok: MagicMock,
        list_history: MagicMock,
        build_valuation: MagicMock,
        build_moneyflow: MagicMock,
    ) -> None:
        list_history.return_value = [object()] * 200
        build_valuation.return_value = MagicMock(pe_percentile_3y=50.0, pb_percentile_3y=40.0)
        build_moneyflow.return_value = MagicMock(history=[], message="")

        financial = MagicMock()
        financial.get_bundle.return_value = MagicMock(snapshots=[], sync_meta=None)
        engine = MagicMock(financial_service=financial)

        technical = {
            "as_of": "2024-06-01",
            "last_close": 10.5,
            "bars_used": 80,
            "warnings": [],
        }
        dashboard = build_overview_dashboard(engine, "600000.SSE", technical=technical)
        labels = [item.label for item in dashboard.readiness]
        self.assertEqual(labels, ["日K", "短线", "财报", "估值", "资金流", "股东"])
        daily = dashboard.readiness[0]
        self.assertEqual(daily.status, "ready")
        self.assertEqual(dashboard.readiness[3].status, "ready")
        self.assertEqual(dashboard.readiness[4].status, "unconfigured")


if __name__ == "__main__":
    unittest.main()
