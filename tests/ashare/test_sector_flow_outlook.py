"""板块未来 N 日延续展望测试。"""

from __future__ import annotations

import unittest
from unittest import mock

from vnpy_ashare.domain.market.sector_flow import (
    SectorFlowHistoryPoint,
    SectorFlowRotationRow,
    SectorFlowRotationSnapshot,
    SectorFlowRow,
)
from vnpy_ashare.services.sector_flow_outlook import (
    build_continuation_outlook,
    filter_outlook_rows,
    format_continuation_ai_lines,
)


def _sector_row(sector_id: str, name: str) -> SectorFlowRow:
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


def _rotation_row(pattern: str, *, momentum_delta: float = 2.0, rank_delta: int = 2) -> SectorFlowRotationRow:
    points = tuple(SectorFlowHistoryPoint(trade_date=f"202409{i:02d}", net_flow_yi=1.0) for i in range(1, 16))
    return SectorFlowRotationRow(
        sector=_sector_row("BK001", "半导体"),
        points=points,
        cumulative_net_yi=15.0,
        positive_days=12,
        flow_pattern=pattern,
        momentum_delta=momentum_delta,
        rank_delta=rank_delta,
    )


class SectorFlowContinuationOutlookTests(unittest.TestCase):
    def test_build_continuation_outlook_continuous_inflow(self) -> None:
        rotation = SectorFlowRotationSnapshot(
            trade_dates=tuple(f"202409{i:02d}" for i in range(1, 16)),
            rows=(_rotation_row("持续流入"),),
            sector_kind="industry",
        )
        with mock.patch(
            "vnpy_ashare.services.sector_flow_outlook.iter_forward_trade_date_strs",
            return_value=("20240916", "20240917", "20240918"),
        ):
            outlook = build_continuation_outlook(rotation)
        self.assertEqual(len(outlook.rows), 1)
        row = outlook.rows[0]
        self.assertEqual(row.headline_pattern, "持续流入")
        self.assertEqual(row.days[0].bias, "偏多")
        self.assertGreater(row.days[0].strength, row.days[2].strength)

    def test_filter_outlook_rows_by_bias(self) -> None:
        rotation = SectorFlowRotationSnapshot(
            trade_dates=tuple(f"202409{i:02d}" for i in range(1, 16)),
            rows=(
                _rotation_row("持续流入"),
                _rotation_row("持续流出", momentum_delta=-3.0, rank_delta=-2),
            ),
            sector_kind="industry",
        )
        with mock.patch(
            "vnpy_ashare.services.sector_flow_outlook.iter_forward_trade_date_strs",
            return_value=("20240916", "20240917", "20240918"),
        ):
            outlook = build_continuation_outlook(rotation)
        bullish = filter_outlook_rows(outlook.rows, "偏多")
        self.assertEqual(len(bullish), 1)
        self.assertEqual(bullish[0].sector.name, "半导体")

    def test_format_continuation_ai_lines(self) -> None:
        rotation = SectorFlowRotationSnapshot(
            trade_dates=tuple(f"202409{i:02d}" for i in range(1, 16)),
            rows=(_rotation_row("震荡", momentum_delta=0.0, rank_delta=0),),
            sector_kind="industry",
        )
        with mock.patch(
            "vnpy_ashare.services.sector_flow_outlook.iter_forward_trade_date_strs",
            return_value=("20240916", "20240917", "20240918"),
        ):
            outlook = build_continuation_outlook(rotation)
        lines = format_continuation_ai_lines(outlook, limit=2)
        self.assertTrue(any("未来3日" in line for line in lines))
        self.assertTrue(any("半导体" in line for line in lines))


if __name__ == "__main__":
    unittest.main()
