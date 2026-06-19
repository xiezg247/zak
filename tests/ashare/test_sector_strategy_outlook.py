"""单板块策略扫描与共振测试。"""

from __future__ import annotations

import unittest

from vnpy_ashare.domain.market.sector_flow import (
    SectorFlowOutlookDay,
    SectorFlowOutlookRow,
    SectorFlowRow,
)
from vnpy_ashare.services.sector_flow_outlook_strategy import classify_sector_resonance


def _sector_row() -> SectorFlowRow:
    return SectorFlowRow(
        sector_id="BK001",
        name="半导体",
        strength=1.0,
        change_pct=1.0,
        net_flow_yi=1.0,
        stock_count=10,
        up_ratio=0.5,
        flow_source="dc_industry",
        sector_kind="industry",
    )


def _outlook_row(bias: str) -> SectorFlowOutlookRow:
    return SectorFlowOutlookRow(
        sector=_sector_row(),
        days=(SectorFlowOutlookDay(trade_date="20240916", bias=bias, strength=0.7),),
        headline_pattern="测试",
        rationale="测试",
        source="continuation",
    )


class SectorStrategyResonanceTests(unittest.TestCase):
    def test_classify_sector_resonance_aligned(self) -> None:
        agreement = classify_sector_resonance(_outlook_row("偏多"), _outlook_row("偏多"))
        self.assertEqual(agreement, "同向")

    def test_classify_sector_resonance_diverged(self) -> None:
        agreement = classify_sector_resonance(_outlook_row("偏多"), _outlook_row("偏空"))
        self.assertEqual(agreement, "背离")


if __name__ == "__main__":
    unittest.main()
