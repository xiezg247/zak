"""flow_pattern 与 stock_continuation 单元测试。"""

from __future__ import annotations

import unittest
from unittest import mock

from vnpy_ashare.domain.market.flow_pattern import classify_flow_pattern_values
from vnpy_ashare.domain.market.sector_flow import SectorFlowOutlookDay, SectorFlowOutlookRow, SectorFlowRow
from vnpy_ashare.domain.trading.signal_snapshot import SignalSnapshot
from vnpy_ashare.domain.trading.stock_continuation import format_outlook_compact
from vnpy_ashare.services.signals.stock_continuation import (
    build_stock_continuation,
    format_continuation_context_extra,
    format_signal_panel_context_extra,
)


def _snapshot(**kwargs) -> SignalSnapshot:
    base = {
        "vt_symbol": "600000.SSE",
        "strategy_id": "AshareShortBreakoutStrategy",
        "as_of": "2024-06-20",
        "signal": "buy",
        "signal_label": "买入",
        "signal_date": "2024-06-20",
        "ref_buy_price": 10.0,
        "ref_sell_price": 11.0,
        "strength": 80.0,
        "reason_summary": "测试",
        "reasons": ("测试理由",),
        "warnings": (),
        "ma_gap_pct": 2.5,
        "volume_ratio_5d": 1.5,
        "relative_index_pct": 1.2,
    }
    base.update(kwargs)
    return SignalSnapshot(**base)


def _sector_outlook(name: str = "银行") -> SectorFlowOutlookRow:
    sector = SectorFlowRow(
        sector_id="BK0475",
        name=name,
        strength=1.0,
        change_pct=1.0,
        net_flow_yi=3.0,
        stock_count=10,
        up_ratio=0.5,
        flow_source="dc_industry",
        sector_kind="industry",
    )
    days = (
        SectorFlowOutlookDay(trade_date="20240621", bias="偏多", strength=0.7),
        SectorFlowOutlookDay(trade_date="20240624", bias="偏多", strength=0.5),
        SectorFlowOutlookDay(trade_date="20240625", bias="震荡", strength=0.4),
    )
    return SectorFlowOutlookRow(
        sector=sector,
        days=days,
        headline_pattern="持续流入",
        rationale="测试",
        source="continuation",
    )


class FlowPatternValuesTests(unittest.TestCase):
    def test_continuous_inflow(self) -> None:
        values = [1.0] * 10 + [5.0] * 5
        self.assertEqual(classify_flow_pattern_values(values), "持续流入")

    def test_in_then_out(self) -> None:
        values = [2.0] * 7 + [-2.0] * 8
        self.assertEqual(classify_flow_pattern_values(values), "先入后出")


class StockContinuationTests(unittest.TestCase):
    def test_buy_fresh_produces_price_continuation(self) -> None:
        continuation = build_stock_continuation(_snapshot())
        self.assertIsNotNone(continuation)
        assert continuation is not None
        self.assertEqual(continuation.headline_pattern, "价量延续")
        self.assertEqual(len(continuation.outlook_days), 3)
        self.assertEqual(continuation.outlook_days[0].bias, "偏多")
        self.assertIn("价量", continuation.rationale)

    def test_expired_buy_produces_decay(self) -> None:
        continuation = build_stock_continuation(_snapshot(signal_date="2024-06-01", ma_gap_pct=-1.0, volume_ratio_5d=0.6))
        self.assertIsNotNone(continuation)
        assert continuation is not None
        self.assertEqual(continuation.headline_pattern, "动能衰减")

    def test_moneyflow_overrides_headline(self) -> None:
        values = [1000.0] * 10 + [5000.0] * 5
        continuation = build_stock_continuation(_snapshot(), moneyflow_values=values)
        self.assertIsNotNone(continuation)
        assert continuation is not None
        self.assertEqual(continuation.moneyflow_pattern, "持续流入")
        self.assertEqual(continuation.headline_pattern, "持续流入")

    def test_price_moneyflow_conflict_becomes_sideways(self) -> None:
        values = [-1000.0] * 10 + [-5000.0] * 5
        continuation = build_stock_continuation(_snapshot(), moneyflow_values=values)
        self.assertIsNotNone(continuation)
        assert continuation is not None
        self.assertEqual(continuation.headline_pattern, "震荡")
        self.assertIn("分歧", continuation.rationale)

    def test_sector_context_attached(self) -> None:
        continuation = build_stock_continuation(
            _snapshot(),
            industry="银行",
            sector_outlook=_sector_outlook(),
        )
        self.assertIsNotNone(continuation)
        assert continuation is not None
        self.assertEqual(continuation.sector_name, "银行")
        self.assertEqual(continuation.sector_pattern, "持续流入")
        self.assertEqual(continuation.sector_outlook_compact, "多/多/震")
        self.assertEqual(continuation.sector_id, "BK0475")

    def test_format_outlook_compact(self) -> None:
        continuation = build_stock_continuation(_snapshot())
        text = format_outlook_compact(continuation)
        self.assertRegex(text, r"^[多空震](/[多空震]){0,2}$")

    def test_format_continuation_context_extra(self) -> None:
        continuation = build_stock_continuation(
            _snapshot(),
            industry="银行",
            sector_outlook=_sector_outlook(),
        )
        text = format_continuation_context_extra(continuation)
        assert continuation is not None
        self.assertIn("延续模式", text)
        self.assertIn("未来3日", text)
        self.assertIn("板块环境", text)
        self.assertIn("统计情景", text)

    def test_format_signal_panel_context_extra_merges_sections(self) -> None:
        continuation = build_stock_continuation(_snapshot())
        text = format_signal_panel_context_extra(_snapshot(), continuation)
        self.assertIn("策略信号", text)
        self.assertIn("【个股延续】", text)

    def test_missing_kline_returns_none(self) -> None:
        continuation = build_stock_continuation(_snapshot(signal="na", warnings=("暂无足够 K 线",)))
        self.assertIsNone(continuation)


class StockContinuationBatchTests(unittest.TestCase):
    @mock.patch("vnpy_ashare.services.signals.stock_continuation.get_stock_industry_map", return_value={})
    @mock.patch("vnpy_ashare.services.signals.stock_continuation._load_sector_outlook_by_name", return_value={})
    @mock.patch("vnpy_ashare.services.signals.stock_continuation.load_stock_moneyflow_values", return_value=[])
    def test_batch_build(self, _mf: mock.Mock, _sector: mock.Mock, _industry: mock.Mock) -> None:
        from vnpy_ashare.services.signals.stock_continuation import build_continuation_batch

        cache = {"600000.SSE": _snapshot()}
        result = build_continuation_batch(["600000.SSE"], cache, include_sector_context=False)
        self.assertIn("600000.SSE", result)


if __name__ == "__main__":
    unittest.main()
