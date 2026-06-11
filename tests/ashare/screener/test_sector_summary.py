"""板块汇总测试。"""

from __future__ import annotations

from vnpy_ashare.screener.sector.sector_summary import compute_sector_distribution, top_industries_by_momentum


def test_compute_sector_distribution():
    rows = [
        {"industry": "银行", "change_pct": 2.0},
        {"industry": "银行", "change_pct": 4.0},
        {"industry": "白酒", "change_pct": 1.0},
        {"industry": "白酒", "change_pct": 3.0},
    ]
    stats = compute_sector_distribution(rows, top_n=2, min_stocks=2)
    assert len(stats) == 2
    assert stats[0]["industry"] == "银行"
    assert stats[0]["avg_change_pct"] == 3.0


def test_top_industries_by_momentum():
    rows = [
        {"industry": "银行", "change_pct": 5.0},
        {"industry": "银行", "change_pct": 3.0},
        {"industry": "银行", "change_pct": 4.0},
        {"industry": "钢铁", "change_pct": -1.0},
        {"industry": "钢铁", "change_pct": 0.0},
        {"industry": "钢铁", "change_pct": 1.0},
    ]
    industries = top_industries_by_momentum(rows, top_industry_count=1, min_stocks_per_industry=3)
    assert industries == ["银行"]
