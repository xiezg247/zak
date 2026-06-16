"""投研团队规则评分测试。"""

from __future__ import annotations

from vnpy_llm.graph.team_scoring import compute_team_scores, score_financial, score_risk, score_strategy


def test_score_financial_high_quality():
    result = score_financial(
        {
            "latest_financials": {"roe": 18.0, "net_income_yoy": 15.0, "debt_ratio": 40.0},
            "valuation": {"pe_ttm": 15.0},
        }
    )
    assert result["score"] >= 80
    assert any("ROE" in h for h in result["highlights"])


def test_score_financial_error():
    assert score_financial({"error": "无数据"})["score"] == 0


def test_score_risk_low_volatility():
    result = score_risk(
        {
            "volatility_annualized_pct": 20.0,
            "max_drawdown_pct": 15.0,
            "return_pct_60d": 12.0,
        }
    )
    assert result["score"] >= 75


def test_score_strategy_bullish():
    result = score_strategy(
        {
            "technical": {"ma_alignment": "多头排列", "period_return": {"return_pct": 8.0}},
            "strategy_signals": {"signal": "buy"},
        }
    )
    assert result["score"] >= 70
    assert "多头" in result["summary"]


def test_compute_team_scores_weighted():
    prefetch = {
        "financial": {"latest_financials": {"roe": 10.0}, "valuation": {}},
        "risk": {"volatility_annualized_pct": 30.0, "max_drawdown_pct": 25.0},
        "strategy": {"technical": {"ma_alignment": "中性"}},
    }
    scores = compute_team_scores(prefetch)
    assert "financial" in scores
    assert "risk" in scores
    assert "strategy" in scores
    assert isinstance(scores["weighted"], float)
