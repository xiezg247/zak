"""DepthSnapshot 领域测试。"""

from __future__ import annotations

from vnpy_ashare.domain.market.depth_snapshot import DepthSnapshot


def test_depth_snapshot_levels() -> None:
    depth = DepthSnapshot(
        symbol="600000",
        bid_prices=[10.0, 9.9],
        bid_volumes=[100, 200],
        ask_prices=[10.1, 10.2],
        ask_volumes=[150, 250],
    )
    assert depth.bid_levels()[0] == (1, 10.0, 100)
    assert depth.ask_levels()[0][0] == 2
