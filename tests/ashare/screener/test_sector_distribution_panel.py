"""行业分布面板测试。"""

from __future__ import annotations

from unittest.mock import patch

from vnpy_ashare.screener.data.screening_status import format_sector_insight


def test_format_sector_insight_groups_by_industry() -> None:
    rows = [
        {"vt_symbol": "600000.SH", "industry": "银行", "change_pct": 1.0},
        {"vt_symbol": "600016.SH", "industry": "银行", "change_pct": 2.0},
        {"vt_symbol": "600519.SH", "industry": "白酒", "change_pct": -1.0},
    ]
    with patch(
        "vnpy_ashare.screener.data.screening_status.attach_industry",
        side_effect=lambda rows, industry_map=None: rows,
    ):
        text = format_sector_insight(rows, top_n=2)
    assert "行业分布" in text
    assert "银行" in text


def test_sector_distribution_stats() -> None:
    from vnpy_ashare.screener.sector.sector_summary import compute_sector_distribution

    stats = compute_sector_distribution(
        [
            {"industry": "银行", "change_pct": 1.0},
            {"industry": "银行", "change_pct": 3.0},
            {"industry": "白酒", "change_pct": -2.0},
        ],
        top_n=3,
        min_stocks=1,
    )
    assert stats[0]["industry"] == "银行"
    assert stats[0]["count"] == 2
    assert stats[0]["advance_pct"] == 100.0
