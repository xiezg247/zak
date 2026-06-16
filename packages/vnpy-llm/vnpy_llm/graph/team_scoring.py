"""投研团队：基于预取事实的规则评分（供 chief 与子 Agent 参考）。"""

from __future__ import annotations

from typing import Any


def _clamp(score: int) -> int:
    return max(0, min(100, score))


def score_financial(financial: dict[str, Any]) -> dict[str, Any]:
    if financial.get("error"):
        return {"score": 0, "summary": "财务数据不可用"}

    score = 50
    highlights: list[str] = []
    risks: list[str] = []

    latest = financial.get("latest_financials") or {}
    valuation = financial.get("valuation") or {}

    roe = latest.get("roe")
    if roe is not None:
        if roe >= 15:
            score += 15
            highlights.append(f"ROE {roe:.1f}%")
        elif roe >= 8:
            score += 8
        else:
            score -= 5
            risks.append(f"ROE 偏低 {roe:.1f}%")

    pe = valuation.get("pe_ttm")
    if pe is not None and pe > 0:
        if pe < 20:
            score += 10
            highlights.append(f"PE(TTM) {pe:.1f}")
        elif pe > 50:
            score -= 10
            risks.append(f"PE(TTM) 偏高 {pe:.1f}")

    yoy = latest.get("net_income_yoy")
    if yoy is not None:
        if yoy >= 10:
            score += 10
            highlights.append(f"净利润同比 {yoy:.1f}%")
        elif yoy < -10:
            score -= 10
            risks.append(f"净利润同比下滑 {yoy:.1f}%")

    debt = latest.get("debt_ratio")
    if debt is not None:
        if debt < 50:
            score += 5
        elif debt > 70:
            score -= 5
            risks.append(f"资产负债率 {debt:.1f}%")

    return {
        "score": _clamp(score),
        "summary": "；".join(highlights) if highlights else "财务数据有限",
        "highlights": highlights,
        "risks": risks,
    }


def score_risk(risk: dict[str, Any]) -> dict[str, Any]:
    """分数越高表示越安全（低风险）。"""
    if risk.get("error"):
        return {"score": 0, "summary": "风险数据不可用"}

    score = 60
    highlights: list[str] = []
    risks: list[str] = []

    vol = risk.get("volatility_annualized_pct")
    if vol is not None:
        if vol < 25:
            score += 15
            highlights.append(f"年化波动 {vol:.1f}%")
        elif vol > 40:
            score -= 15
            risks.append(f"波动偏高 {vol:.1f}%")

    dd = risk.get("max_drawdown_pct")
    if dd is not None:
        if dd < 20:
            score += 10
            highlights.append(f"最大回撤 {dd:.1f}%")
        elif dd > 35:
            score -= 15
            risks.append(f"回撤较大 {dd:.1f}%")

    ret = risk.get("return_pct_60d")
    if ret is not None:
        if ret >= 10:
            score += 5
        elif ret <= -15:
            score -= 10
            risks.append(f"近60日跌 {ret:.1f}%")

    beta = risk.get("beta")
    if beta is not None:
        if abs(beta) <= 1.0:
            score += 5
            highlights.append(f"Beta {beta:.2f}")
        elif beta >= 1.3:
            score -= 10
            risks.append(f"Beta 偏高 {beta:.2f}")

    sentiment = risk.get("market_sentiment") or {}
    fg = sentiment.get("fear_greed_index")
    if fg is not None:
        if fg >= 75:
            score -= 5
            risks.append(f"市场贪婪 {fg:.0f}")
        elif fg <= 25:
            score += 5
            highlights.append(f"市场恐惧 {fg:.0f}")

    return {
        "score": _clamp(score),
        "summary": "；".join(highlights) if highlights else "风险指标有限",
        "highlights": highlights,
        "risks": risks,
    }


def score_strategy(strategy: dict[str, Any]) -> dict[str, Any]:
    if strategy.get("error"):
        return {"score": 0, "summary": "策略数据不可用"}

    score = 50
    highlights: list[str] = []
    risks: list[str] = []

    technical = strategy.get("technical") or {}
    signals = strategy.get("strategy_signals") or {}

    alignment = str(technical.get("ma_alignment") or "")
    if "多头" in alignment:
        score += 20
        highlights.append(alignment)
    elif "空头" in alignment:
        score -= 15
        risks.append(alignment)

    signal = str(signals.get("signal") or signals.get("snapshot", {}).get("signal") or "")
    if signal == "buy":
        score += 15
        highlights.append("策略信号偏多")
    elif signal == "sell":
        score -= 15
        risks.append("策略信号偏空")

    ret = (technical.get("period_return") or {}).get("return_pct")
    if ret is not None and ret >= 5:
        score += 5

    return {
        "score": _clamp(score),
        "summary": "；".join(highlights) if highlights else "技术面中性",
        "highlights": highlights,
        "risks": risks,
    }


def score_market(market_context: dict[str, Any]) -> dict[str, Any]:
    """分数越高表示标的相对市场环境越占优。"""
    if not market_context or market_context.get("error"):
        return {"score": 50, "summary": "市场环境数据有限", "highlights": [], "risks": []}

    score = 50
    highlights: list[str] = []
    risks: list[str] = []

    stock_vs = market_context.get("stock_vs_benchmark") or {}
    excess = stock_vs.get("excess_pct")
    if excess is not None:
        if excess >= 8:
            score += 15
            highlights.append(f"相对沪深300超额 {excess:+.1f}%")
        elif excess >= 3:
            score += 8
            highlights.append(f"相对沪深300超额 {excess:+.1f}%")
        elif excess <= -8:
            score -= 15
            risks.append(f"相对沪深300落后 {excess:+.1f}%")
        elif excess <= -3:
            score -= 8
            risks.append(f"相对沪深300落后 {excess:+.1f}%")

    sector = market_context.get("sector") or {}
    rank = sector.get("rank")
    total_sectors = sector.get("total_sectors")
    avg_change = sector.get("avg_change_pct")
    if rank is not None and isinstance(total_sectors, int) and total_sectors > 0:
        if rank <= 3:
            score += 10
            highlights.append(f"行业当日涨幅第 {rank}/{total_sectors}")
        elif rank >= max(1, total_sectors - 2):
            score -= 8
            risks.append(f"行业当日涨幅靠后 {rank}/{total_sectors}")
    if avg_change is not None and avg_change >= 2:
        score += 5
        highlights.append(f"行业均涨 {avg_change:+.1f}%")
    elif avg_change is not None and avg_change <= -2:
        score -= 5
        risks.append(f"行业均跌 {avg_change:+.1f}%")

    sentiment = market_context.get("market_sentiment") or {}
    fg = sentiment.get("fear_greed_index")
    if fg is not None:
        if fg >= 80:
            score -= 5
            risks.append(f"市场偏贪婪 {fg:.0f}")
        elif fg <= 20:
            score += 5
            highlights.append(f"市场偏恐惧 {fg:.0f}")

    summary_lines = market_context.get("summary_lines") or []
    summary = "；".join(highlights) if highlights else (
        str(summary_lines[0]) if summary_lines else "市场环境中性"
    )

    return {
        "score": _clamp(score),
        "summary": summary,
        "highlights": highlights,
        "risks": risks,
    }


def compute_team_scores(prefetch: dict[str, Any]) -> dict[str, Any]:
    financial = score_financial(prefetch.get("financial") or {})
    risk = score_risk(prefetch.get("risk") or {})
    strategy = score_strategy(prefetch.get("strategy") or {})
    market = score_market(prefetch.get("market_context") or {})

    weighted = round(
        financial["score"] * 0.35
        + risk["score"] * 0.25
        + strategy["score"] * 0.20
        + market["score"] * 0.20,
        1,
    )

    return {
        "financial": financial,
        "risk": risk,
        "strategy": strategy,
        "market": market,
        "weighted": weighted,
        "weights": {
            "financial": 0.35,
            "risk": 0.25,
            "strategy": 0.20,
            "market": 0.20,
        },
    }
