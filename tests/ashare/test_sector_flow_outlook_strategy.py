"""板块未来 N 日策略聚合展望测试。"""

from __future__ import annotations

import unittest
from unittest import mock

from vnpy_ashare.domain.market.sector_flow import SectorFlowRow, SectorFlowSnapshot
from vnpy_ashare.domain.radar.card import RadarRow
from vnpy_ashare.domain.radar.horizon_cache import HorizonCacheEntry
from vnpy_ashare.services.sector_flow_outlook_strategy import build_strategy_outlook


def _sector_row(sector_id: str, name: str) -> SectorFlowRow:
    return SectorFlowRow(
        sector_id=sector_id,
        name=name,
        strength=1.0,
        change_pct=1.0,
        net_flow_yi=1.0,
        stock_count=10,
        up_ratio=0.5,
        flow_source="dc_industry",
        sector_kind="industry",
    )


def _snapshot() -> SectorFlowSnapshot:
    row = _sector_row("BK001", "半导体")
    return SectorFlowSnapshot(
        rows=(row,),
        inflow_rows=(row,),
        outflow_rows=(),
        sector_kind="industry",
        data_mode="official_dc",
    )


class SectorFlowStrategyOutlookTests(unittest.TestCase):
    def test_build_strategy_outlook_aggregates_hits(self) -> None:
        watch_entry = HorizonCacheEntry(
            variant="watch_next",
            rows=(
                RadarRow(
                    vt_symbol="600000.SH",
                    name="浦发银行",
                    symbol="600000",
                    price=10.0,
                    change_pct=1.0,
                    metric_label="买入",
                    metric_value="80",
                    sub_label="判断",
                    sub_value="金叉",
                ),
            ),
            scanned_total=1,
            excluded_count=0,
            prefilter_total=1,
            refined_total=1,
            kline_missing=0,
            strategy_key="test",
            computed_at="2024-09-16 15:00",
        )
        with mock.patch(
            "vnpy_ashare.services.sector_flow_outlook_strategy.iter_forward_trade_date_strs",
            return_value=("20240916", "20240917", "20240918"),
        ):
            with mock.patch(
                "vnpy_ashare.services.sector_flow_outlook_strategy._sector_member_symbols",
                return_value={"600000.SH", "600001.SH", "600002.SH"},
            ):
                outlook = build_strategy_outlook(
                    _snapshot(),
                    strategy_key="test",
                    watch_entry=watch_entry,
                    hold_entry=None,
                )
        self.assertEqual(len(outlook.rows), 1)
        row = outlook.rows[0]
        self.assertIn("买入1", row.headline_pattern)
        self.assertIn(row.days[0].bias, {"偏多", "震荡"})
        self.assertGreater(row.days[0].strength, 0.0)

    def test_build_strategy_outlook_empty_cache_hint(self) -> None:
        with mock.patch(
            "vnpy_ashare.services.sector_flow_outlook_strategy.iter_forward_trade_date_strs",
            return_value=("20240916", "20240917", "20240918"),
        ):
            with mock.patch(
                "vnpy_ashare.services.sector_flow_outlook_strategy._sector_member_symbols",
                return_value={"600000.SH"},
            ):
                with mock.patch(
                    "vnpy_ashare.quotes.radar.radar_horizon_cache.get_horizon_cache",
                    return_value=None,
                ):
                    outlook = build_strategy_outlook(_snapshot(), strategy_key="test")
        self.assertIn("扫描策略B", outlook.empty_hint)
        self.assertEqual(len(outlook.rows), 0)


    def test_strategy_outlook_cache_fresh_and_expired(self) -> None:
        from datetime import timedelta

        from vnpy_ashare.domain.radar.horizon_cache import HorizonCacheEntry
        from vnpy_ashare.domain.time.china import china_now, format_china_datetime_minute
        from vnpy_ashare.services.sector_flow_outlook_strategy import (
            strategy_outlook_cache_expired,
            strategy_outlook_cache_fresh,
            strategy_outlook_cache_ready,
        )

        fresh_at = format_china_datetime_minute(china_now())
        stale_at = format_china_datetime_minute(china_now() - timedelta(hours=30))
        entry = HorizonCacheEntry(
            variant="watch_next",
            rows=(),
            scanned_total=1,
            excluded_count=0,
            prefilter_total=1,
            refined_total=0,
            kline_missing=0,
            strategy_key="test_key",
            computed_at=fresh_at,
        )
        config = mock.MagicMock()
        config.cache_key.return_value = "test_key"
        with mock.patch(
            "vnpy_ashare.services.sector_flow_outlook_strategy.resolve_strategy_signal_config",
            return_value=config,
        ):
            with mock.patch(
                "vnpy_ashare.services.sector_flow_outlook_strategy._strategy_horizon_cache_entries",
                return_value=(entry, None),
            ):
                self.assertTrue(strategy_outlook_cache_ready("AshareDoubleMaStrategy"))
                self.assertTrue(strategy_outlook_cache_fresh("AshareDoubleMaStrategy"))
                self.assertFalse(strategy_outlook_cache_expired("AshareDoubleMaStrategy"))
            stale_entry = entry.model_copy(update={"computed_at": stale_at})
            with mock.patch(
                "vnpy_ashare.services.sector_flow_outlook_strategy._strategy_horizon_cache_entries",
                return_value=(stale_entry, None),
            ):
                self.assertTrue(strategy_outlook_cache_ready("AshareDoubleMaStrategy"))
                self.assertFalse(strategy_outlook_cache_fresh("AshareDoubleMaStrategy"))
                self.assertTrue(strategy_outlook_cache_expired("AshareDoubleMaStrategy"))


if __name__ == "__main__":
    unittest.main()
