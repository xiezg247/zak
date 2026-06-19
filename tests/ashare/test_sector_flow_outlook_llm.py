"""板块未来展望 C（LLM）测试。"""

from __future__ import annotations

import json
import unittest
from unittest import mock

from vnpy_ashare.domain.market.sector_flow import (
    SectorFlowOutlookBundle,
    SectorFlowOutlookCompareRow,
    SectorFlowOutlookDay,
    SectorFlowOutlookRow,
    SectorFlowOutlookSnapshot,
    SectorFlowRow,
    SectorFlowSnapshot,
)
from vnpy_ashare.services.sector_flow_outlook_llm import (
    outlook_bundle_fingerprint,
    parse_llm_outlook_response,
)


def _sector_row(sector_id: str = "BK001", name: str = "半导体") -> SectorFlowRow:
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


def _outlook_row(
    bias: str = "偏多",
    *,
    sector: SectorFlowRow | None = None,
    source: str = "continuation",
) -> SectorFlowOutlookRow:
    sector = sector or _sector_row()
    return SectorFlowOutlookRow(
        sector=sector,
        days=(
            SectorFlowOutlookDay(trade_date="20240916", bias=bias, strength=0.7),
            SectorFlowOutlookDay(trade_date="20240917", bias="震荡", strength=0.5),
            SectorFlowOutlookDay(trade_date="20240918", bias="震荡", strength=0.3),
        ),
        headline_pattern="测试",
        rationale="测试说明",
        source=source,
    )


def _bundle() -> SectorFlowOutlookBundle:
    continuation = SectorFlowOutlookSnapshot(
        forward_dates=("20240916", "20240917", "20240918"),
        rows=(_outlook_row("偏多"),),
        sector_kind="industry",
        source="continuation",
    )
    strategy = SectorFlowOutlookSnapshot(
        forward_dates=("20240916", "20240917", "20240918"),
        rows=(_outlook_row("偏多", source="strategy"),),
        sector_kind="industry",
        source="strategy",
    )
    compare_rows = (
        SectorFlowOutlookCompareRow(
            sector=_sector_row(),
            continuation=continuation.rows[0],
            strategy=strategy.rows[0],
            agreement="一致",
        ),
    )
    return SectorFlowOutlookBundle(
        continuation=continuation,
        strategy=strategy,
        compare_rows=compare_rows,
    )


class SectorFlowOutlookLlmTests(unittest.TestCase):
    def test_outlook_bundle_fingerprint_stable(self) -> None:
        bundle = _bundle()
        with mock.patch(
            "vnpy_ashare.services.sector_flow_outlook_llm.resolve_strategy_signal_config",
        ) as resolve_mock:
            config = mock.MagicMock()
            config.cache_key.return_value = "test_key"
            resolve_mock.return_value = config
            first = outlook_bundle_fingerprint(bundle, strategy_class="AshareDoubleMaStrategy")
            second = outlook_bundle_fingerprint(bundle, strategy_class="AshareDoubleMaStrategy")
        self.assertEqual(first, second)
        self.assertEqual(len(first), 24)

    def test_parse_llm_outlook_response_json(self) -> None:
        bundle = _bundle()
        payload = {
            "sectors": [
                {
                    "sector_id": "BK001",
                    "days": [
                        {"trade_date": "20240916", "bias": "偏多", "strength": 0.66},
                        {"trade_date": "20240917", "bias": "震荡", "strength": 0.44},
                        {"trade_date": "20240918", "bias": "偏空", "strength": 0.35},
                    ],
                    "headline": "动量延续",
                    "rationale": "延续与策略一致，短线偏多情景",
                }
            ]
        }
        rows = parse_llm_outlook_response(
            json.dumps(payload),
            bundle=bundle,
            forward_dates=("20240916", "20240917", "20240918"),
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].source, "llm")
        self.assertEqual(rows[0].days[0].bias, "偏多")
        self.assertEqual(rows[0].headline_pattern, "动量延续")

    def test_parse_llm_outlook_response_rejects_empty(self) -> None:
        bundle = _bundle()
        with self.assertRaises(ValueError):
            parse_llm_outlook_response('{"sectors":[]}', bundle=bundle, forward_dates=("20240916",))


if __name__ == "__main__":
    unittest.main()
