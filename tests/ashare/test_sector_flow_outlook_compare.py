"""板块未来 N 日展望对照测试。"""

from __future__ import annotations

import unittest

from vnpy_ashare.domain.market.sector_flow import (
    SectorFlowOutlookDay,
    SectorFlowOutlookRow,
    SectorFlowOutlookSnapshot,
    SectorFlowRow,
)
from vnpy_ashare.services.sector_flow_outlook_compare import (
    build_outlook_compare_rows,
    classify_outlook_agreement,
    filter_compare_rows,
)


def _sector_row(name: str = "半导体", *, sector_id: str = "BK001") -> SectorFlowRow:
    return SectorFlowRow(
        sector_id=sector_id,
        name=name,
        strength=1.0,
        change_pct=1.0,
        net_flow_yi=1.0,
        stock_count=3,
        up_ratio=0.5,
        flow_source="dc_industry",
        sector_kind="industry",
    )


def _outlook_row(bias: str, *, source: str = "continuation") -> SectorFlowOutlookRow:
    return SectorFlowOutlookRow(
        sector=_sector_row(),
        days=(
            SectorFlowOutlookDay(trade_date="20240916", bias=bias, strength=0.7),
            SectorFlowOutlookDay(trade_date="20240917", bias=bias, strength=0.5),
            SectorFlowOutlookDay(trade_date="20240918", bias="震荡", strength=0.3),
        ),
        headline_pattern="测试",
        rationale="测试说明",
        source=source,
    )


class SectorFlowOutlookCompareTests(unittest.TestCase):
    def test_classify_outlook_agreement(self) -> None:
        self.assertEqual(
            classify_outlook_agreement(_outlook_row("偏多"), _outlook_row("偏多", source="strategy")),
            "一致",
        )
        self.assertEqual(
            classify_outlook_agreement(_outlook_row("偏多"), _outlook_row("偏空", source="strategy")),
            "分歧",
        )

    def test_build_outlook_compare_rows(self) -> None:
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
        rows = build_outlook_compare_rows(continuation, strategy)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].agreement, "一致")

    def test_filter_compare_rows(self) -> None:
        bank_sector = _sector_row("银行", sector_id="BK002")
        continuation = SectorFlowOutlookSnapshot(
            forward_dates=("20240916", "20240917", "20240918"),
            rows=(
                _outlook_row("偏多"),
                SectorFlowOutlookRow(
                    sector=bank_sector,
                    days=_outlook_row("偏空").days,
                    headline_pattern="测试",
                    rationale="测试说明",
                    source="continuation",
                ),
            ),
            sector_kind="industry",
            source="continuation",
        )
        strategy = SectorFlowOutlookSnapshot(
            forward_dates=("20240916", "20240917", "20240918"),
            rows=(
                _outlook_row("偏多", source="strategy"),
                SectorFlowOutlookRow(
                    sector=bank_sector,
                    days=_outlook_row("震荡", source="strategy").days,
                    headline_pattern="测试",
                    rationale="测试说明",
                    source="strategy",
                ),
            ),
            sector_kind="industry",
            source="strategy",
        )
        rows = build_outlook_compare_rows(continuation, strategy)
        agreed = filter_compare_rows(rows, "一致")
        self.assertEqual(len(agreed), 1)


if __name__ == "__main__":
    unittest.main()
