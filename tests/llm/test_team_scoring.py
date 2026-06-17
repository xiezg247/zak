"""投研团队规则评分测试。"""

from __future__ import annotations

from vnpy_llm.graph.team_scoring import compute_team_scores, score_financial, score_market, score_risk, score_strategy


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
            "beta": 0.8,
            "market_sentiment": {"fear_greed_index": 20.0},
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


def test_score_strategy_ultra_short_recession_penalty():
    result = score_strategy(
        {
            "technical": {"ma_alignment": "多头排列"},
            "strategy_signals": {"signal": "buy"},
            "ultra_short": {
                "emotion_stage": "recession",
                "emotion_stage_label": "退潮",
                "allow_new_positions": False,
                "limit_board_signal": "sell",
            },
        }
    )
    assert result["score"] < 70
    assert any("退潮" in item for item in result["risks"])


def test_score_strategy_ultra_short_limit_board_buy():
    result = score_strategy(
        {
            "technical": {"ma_alignment": "中性"},
            "strategy_signals": {"signal": "hold"},
            "ultra_short": {
                "emotion_stage": "climax",
                "emotion_stage_label": "高潮",
                "allow_new_positions": True,
                "limit_board_signal": "buy",
                "limit_board_label": "买入",
            },
        }
    )
    assert any("打板" in item for item in result["highlights"])


def test_score_market_outperform():
    result = score_market(
        {
            "stock_vs_benchmark": {"excess_pct": 10.0},
            "sector": {"industry": "半导体", "rank": 1, "total_sectors": 20, "avg_change_pct": 3.0},
            "market_sentiment": {"fear_greed_index": 18.0},
            "summary_lines": ["沪深300 近60日 +5%"],
        }
    )
    assert result["score"] >= 70
    assert any("超额" in h for h in result["highlights"])


def test_compute_team_scores_weighted():
    prefetch = {
        "financial": {"latest_financials": {"roe": 10.0}, "valuation": {}},
        "risk": {"volatility_annualized_pct": 30.0, "max_drawdown_pct": 25.0},
        "strategy": {"technical": {"ma_alignment": "中性"}},
        "market_context": {
            "stock_vs_benchmark": {"excess_pct": 5.0},
            "sector": {"rank": 2, "total_sectors": 10, "avg_change_pct": 1.0},
        },
    }
    scores = compute_team_scores(prefetch)
    assert "financial" in scores
    assert "risk" in scores
    assert "strategy" in scores
    assert "market" in scores
    assert isinstance(scores["weighted"], float)
    assert scores["weights"]["market"] == 0.20
