"""P4-B/C/D 优化测试。"""

from __future__ import annotations

from unittest.mock import patch

from vnpy_ashare.quotes.radar_cross_refs import build_outlook_cross_ref_suffix
from vnpy_ashare.quotes.radar_models import RadarRow
from vnpy_ashare.quotes.radar_relative_strength import build_relative_strength_subline
from vnpy_ashare.screener.dimensions.intraday_breakout import _quote_breakout_strength
from vnpy_ashare.screener.dimensions.momentum import _momentum_change_allowed
from vnpy_ashare.screener.sector.sector_summary import compute_sector_distribution


def test_compute_sector_distribution_includes_advance_ratio() -> None:
    stats = compute_sector_distribution(
        [
            {"industry": "银行", "change_pct": 1.0},
            {"industry": "银行", "change_pct": 2.0},
            {"industry": "银行", "change_pct": -1.0},
        ],
        min_stocks=2,
    )
    assert stats[0]["industry"] == "银行"
    assert stats[0]["advance_pct"] == 66.7


def test_momentum_change_bounds() -> None:
    assert _momentum_change_allowed(5.0)
    assert not _momentum_change_allowed(0.1)
    assert not _momentum_change_allowed(12.0)


def test_breakout_rejects_large_pullback_from_high() -> None:
    row = {
        "prev_close": 10.0,
        "high_price": 11.0,
        "last_price": 10.7,
        "change_pct": 7.0,
        "volume_ratio": 2.0,
    }
    assert _quote_breakout_strength(row, {}) is None


def test_relative_strength_subline_with_industry() -> None:
    with (
        patch(
            "vnpy_ashare.quotes.radar_relative_strength.get_stock_industry_map",
            return_value={"600000.SH": "银行"},
        ),
        patch(
            "vnpy_ashare.quotes.radar_relative_strength.attach_industry",
            side_effect=lambda rows, industry_map=None: [
                {**row, "industry": "银行"} for row in rows
            ],
        ),
        patch(
            "vnpy_ashare.quotes.radar_relative_strength.market_benchmark_change_pct",
            return_value=1.0,
        ),
        patch(
            "vnpy_ashare.quotes.radar_relative_strength.industry_avg_change_map",
            return_value={"银行": 2.0},
        ),
    ):
        sub = build_relative_strength_subline(
            {"vt_symbol": "600000.SSE", "change_pct": 5.0},
            snapshot_rows=[{"change_pct": 1.0}, {"change_pct": 3.0, "industry": "银行"}],
        )
    assert sub is not None
    assert "行业" in sub[1]
    assert "大盘" in sub[1]


def test_outlook_cross_ref_suffix() -> None:
    rows = (
        RadarRow("600000.SSE", "浦发", "600000", 10.0, 1.0, "买入", "70", "事件", "—"),
    )
    with patch(
        "vnpy_ashare.quotes.radar_cross_refs.latest_recipe_vt_symbols",
        return_value={"600000.SSE"},
    ):
        suffix = build_outlook_cross_ref_suffix(rows)
    assert suffix == "选股重合 1"
