"""板块汇总测试。"""

from __future__ import annotations

from vnpy_ashare.screener.sector.sector_summary import (
    attach_industry,
    compute_sector_distribution,
    top_industries_by_momentum,
)


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


def test_attach_industry_includes_l1():
    rows = [{"vt_symbol": "600362.SSE", "change_pct": 1.0}]
    enriched = attach_industry(
        rows,
        industry_map={"600362.SH": "工业金属"},
        industry_l1_map={"600362.SH": "有色金属"},
    )
    assert len(enriched) == 1
    assert enriched[0]["industry"] == "工业金属"
    assert enriched[0]["industry_l1"] == "有色金属"
