"""Tushare stk_shock 与监管异动合并测试。"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from vnpy_ashare.integrations.tushare.stk_shock import (
    ExchangeRegulatoryRecord,
    parse_deviation_pct_from_reason,
    summarize_exchange_records,
)
from vnpy_ashare.services.stock.regulatory_deviation import (
    RegulatoryDeviationSnapshot,
    assess_regulatory_deviation_for_vt_symbol,
    merge_with_exchange_records,
)


class StkShockParseTest(unittest.TestCase):
    def test_parse_deviation_pct(self) -> None:
        reason = "连续三个交易日内涨跌幅偏离值累计达到20%"
        self.assertAlmostEqual(parse_deviation_pct_from_reason(reason), 20.0)

    def test_summarize_exchange_records(self) -> None:
        records = (
            ExchangeRegulatoryRecord(
                vt_symbol="600000.SSE",
                ts_code="600000.SH",
                trade_date="20260617",
                reason="连续三个交易日内涨跌幅偏离值累计达到20%",
                period="20260615-20260617",
                shock_type="shock",
            ),
        )
        text = summarize_exchange_records(records)
        self.assertIn("异常波动", text)
        self.assertIn("20%", text)


class RegulatoryMergeTest(unittest.TestCase):
    def test_exchange_high_shock_overrides_local_none(self) -> None:
        local = RegulatoryDeviationSnapshot(summary="暂无异动预警")
        records = (
            ExchangeRegulatoryRecord(
                vt_symbol="600000.SSE",
                ts_code="600000.SH",
                trade_date="20260617",
                reason="严重异常波动",
                period="10个交易日",
                shock_type="high_shock",
            ),
        )
        merged = merge_with_exchange_records(local, records)
        self.assertEqual(merged.risk_level, "high")
        self.assertTrue(merged.exchange_high_shock)
        self.assertEqual(merged.data_source, "tushare")

    def test_hybrid_when_local_and_exchange_both_warn(self) -> None:
        local = RegulatoryDeviationSnapshot(
            limit_up_count_10d=3,
            risk_level="watch",
            summary="近 10 日 3 次涨停，距严重异动线还差 1 次",
        )
        records = (
            ExchangeRegulatoryRecord(
                vt_symbol="600000.SSE",
                ts_code="600000.SH",
                trade_date="20260617",
                reason="偏离值累计达到12%",
                period="",
                shock_type="shock",
            ),
        )
        merged = merge_with_exchange_records(local, records)
        self.assertEqual(merged.risk_level, "watch")
        self.assertEqual(merged.data_source, "hybrid")
        self.assertIn("偏离", merged.summary)

    @patch("vnpy_ashare.services.stock.regulatory_deviation.load_recent_exchange_regulatory_for_vt_symbol")
    @patch("vnpy_ashare.services.stock.regulatory_deviation.load_daily_bars_tail", return_value=[])
    def test_for_vt_symbol_tushare_only_when_no_bars(
        self,
        _bars,
        load_exchange,
    ) -> None:
        load_exchange.return_value = (
            ExchangeRegulatoryRecord(
                vt_symbol="600000.SSE",
                ts_code="600000.SH",
                trade_date="20260617",
                reason="偏离值累计达到20%",
                period="",
                shock_type="shock",
            ),
        )
        snapshot = assess_regulatory_deviation_for_vt_symbol("600000.SSE")
        assert snapshot is not None
        self.assertEqual(snapshot.risk_level, "watch")
        self.assertEqual(snapshot.data_source, "tushare")


if __name__ == "__main__":
    unittest.main()
