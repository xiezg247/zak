"""P2 相对放量 / 换手维度测试。"""

from __future__ import annotations

from unittest.mock import patch

from vnpy_ashare.screener.dimensions.turnover import run_turnover
from vnpy_ashare.screener.dimensions.volume_surge import run_volume_surge


def test_volume_surge_prefers_volume_ratio() -> None:
    snapshot = type(
        "Snap",
        (),
        {
            "rows": [
                {
                    "vt_symbol": "600000.SSE",
                    "symbol": "600000",
                    "volume": 1_000_000,
                    "amount": 50_000_000,
                    "change_pct": 1.0,
                    "total_mv": 600_000,
                },
                {
                    "vt_symbol": "000001.SZSE",
                    "symbol": "000001",
                    "volume": 9_000_000,
                    "amount": 80_000_000,
                    "change_pct": 1.0,
                    "total_mv": 600_000,
                },
            ],
            "total": 2,
        },
    )()

    with (
        patch(
            "vnpy_ashare.screener.dimensions.volume_surge.load_screening_quote_snapshot",
            return_value=snapshot,
        ),
        patch(
            "vnpy_ashare.screener.dimensions.volume_surge.get_volume_ratio_map",
            return_value={"600000.SSE": 3.5, "000001.SZSE": 1.2},
        ),
    ):
        hits, scanned = run_volume_surge(2, weight=0.1)

    assert scanned == 2
    assert hits[0].vt_symbol == "600000.SSE"
    assert hits[0].row["relative_volume"] == 3.5


def test_turnover_uses_relative_turnover() -> None:
    snapshot = type(
        "Snap",
        (),
        {
            "rows": [
                {
                    "vt_symbol": "600000.SSE",
                    "symbol": "600000",
                    "turnover_rate": 2.0,
                    "total_mv": 600_000,
                    "amount": 40_000_000,
                },
                {
                    "vt_symbol": "000001.SZSE",
                    "symbol": "000001",
                    "turnover_rate": 8.0,
                    "total_mv": 600_000,
                    "amount": 40_000_000,
                },
            ],
            "total": 2,
        },
    )()

    with (
        patch(
            "vnpy_ashare.screener.dimensions.turnover.load_screening_quote_snapshot",
            return_value=snapshot,
        ),
        patch(
            "vnpy_ashare.screener.dimensions.turnover.get_avg_turnover_map",
            return_value={"600000.SSE": 2.0, "000001.SZSE": 4.0},
        ),
    ):
        hits, scanned = run_turnover(2, weight=0.1)

    assert scanned == 2
    assert hits[0].vt_symbol == "000001.SZSE"
    assert hits[0].row["relative_turnover"] == 2.0
