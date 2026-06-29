"""板块市场快照缓存测试。"""

from __future__ import annotations

import unittest
from unittest import mock

from vnpy_ashare.services.stock.profile import (
    SectorMarketSnapshot,
    build_sector_profile,
    invalidate_sector_market_snapshot,
    load_sector_market_snapshot,
    sync_valuation_history,
)


class SectorMarketSnapshotTests(unittest.TestCase):
    def tearDown(self) -> None:
        invalidate_sector_market_snapshot()

    @mock.patch("vnpy_ashare.services.stock.profile.fetch_daily_pct_map", return_value={"600000.SH": 1.2})
    @mock.patch(
        "vnpy_ashare.services.stock.profile.fetch_daily_basic_with_fallback",
        return_value=([{"ts_code": "600000.SH", "pe_ttm": 5.0, "total_mv": 100000}], "20240620"),
    )
    @mock.patch(
        "vnpy_ashare.services.stock.profile.fetch_stock_industry_map",
        return_value={"600000.SH": "银行"},
    )
    def test_load_sector_market_snapshot_caches(
        self,
        industry_map: mock.Mock,
        daily_basic: mock.Mock,
        pct_map: mock.Mock,
    ) -> None:
        first = load_sector_market_snapshot()
        second = load_sector_market_snapshot()
        self.assertIs(first, second)
        industry_map.assert_called_once()
        daily_basic.assert_called_once()
        pct_map.assert_called_once()

    @mock.patch("vnpy_ashare.services.stock.profile.build_valuation_profile")
    @mock.patch("vnpy_ashare.services.stock.profile._valuation_needs_sync", return_value=False)
    def test_sync_valuation_history_reuses_market(
        self,
        _needs_sync: mock.Mock,
        build_profile: mock.Mock,
    ) -> None:
        market = SectorMarketSnapshot(
            industry_map={"600000.SH": "银行"},
            fund_rows=[{"ts_code": "600000.SH"}],
            trade_date="20240620",
            pct_map={},
        )
        build_profile.return_value = mock.Mock(message="", synced=False, history_days=120)

        sync_valuation_history("600000.SSE", market=market)

        build_profile.assert_called_once_with("600000.SSE", market=market)

    @mock.patch("vnpy_ashare.services.stock.profile.load_sector_market_snapshot")
    def test_build_sector_profile_uses_provided_market(self, load_market: mock.Mock) -> None:
        market = SectorMarketSnapshot(
            industry_map={"600000.SH": "银行"},
            fund_rows=[
                {
                    "ts_code": "600000.SH",
                    "vt_symbol": "600000.SSE",
                    "name": "浦发银行",
                    "pe_ttm": 5.0,
                    "pb": 0.6,
                    "total_mv": 200000,
                }
            ],
            trade_date="20240620",
            pct_map={"600000.SH": 1.5},
        )

        profile = build_sector_profile("600000.SSE", name="浦发银行", market=market)

        load_market.assert_not_called()
        self.assertEqual(profile.industry, "银行")
        self.assertEqual(profile.trade_date, "20240620")


if __name__ == "__main__":
    unittest.main()
