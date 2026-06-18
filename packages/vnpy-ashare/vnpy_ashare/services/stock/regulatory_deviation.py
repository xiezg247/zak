"""监管异动距离评估（10 日涨停次数 / 区间涨幅）。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field
from vnpy.trader.object import BarData

from vnpy_ashare.data.pattern_bars import load_daily_bars_tail
from vnpy_ashare.domain.market.breadth import LIMIT_UP_PCT
from vnpy_ashare.domain.symbols.stock import parse_stock_symbol
from vnpy_common.domain.base import FrozenModel
from vnpy_common.domain.serialize import dump_json

RiskLevel = Literal["none", "watch", "high"]

# A 股严重异动常见阈值（简化，未区分 ST / 20% 板）
LIMIT_UP_COUNT_10D_THRESHOLD = 4
LIMIT_UP_COUNT_10D_WARN = 3
RETURN_10D_THRESHOLD_PCT = 100.0
RETURN_10D_WARN_PCT = 85.0
RETURN_30D_THRESHOLD_PCT = 200.0
RETURN_30D_WARN_PCT = 180.0


class RegulatoryDeviationSnapshot(FrozenModel):
    limit_up_count_10d: int = Field(default=0, description="近 10 交易日涨停次数")
    return_10d_pct: float | None = Field(default=None, description="近 10 交易日累计涨幅 %")
    return_30d_pct: float | None = Field(default=None, description="近 30 交易日累计涨幅 %")
    risk_level: RiskLevel = Field(default="none", description="风险等级")
    summary: str = Field(default="", description="一行摘要")


def _bar_change_pct(bars: list[BarData], index: int) -> float | None:
    if index <= 0 or index >= len(bars):
        return None
    prev_close = float(bars[index - 1].close_price)
    if prev_close <= 0:
        return None
    close = float(bars[index].close_price)
    return (close / prev_close - 1.0) * 100.0


def _cumulative_return_pct(bars: list[BarData], window: int) -> float | None:
    if len(bars) < 2:
        return None
    effective = min(window, len(bars) - 1)
    if effective < 1:
        return None
    base = float(bars[-effective - 1].close_price)
    end = float(bars[-1].close_price)
    if base <= 0:
        return None
    return (end / base - 1.0) * 100.0


def _limit_up_count(bars: list[BarData], window: int) -> int:
    if len(bars) < 2:
        return 0
    start = max(1, len(bars) - window)
    count = 0
    for index in range(start, len(bars)):
        change = _bar_change_pct(bars, index)
        if change is not None and change >= LIMIT_UP_PCT:
            count += 1
    return count


def _classify_risk(
    *,
    limit_up_count_10d: int,
    return_10d_pct: float | None,
    return_30d_pct: float | None,
) -> RiskLevel:
    if limit_up_count_10d >= LIMIT_UP_COUNT_10D_THRESHOLD:
        return "high"
    if return_10d_pct is not None and return_10d_pct >= RETURN_10D_THRESHOLD_PCT:
        return "high"
    if return_30d_pct is not None and return_30d_pct >= RETURN_30D_THRESHOLD_PCT:
        return "high"

    if limit_up_count_10d >= LIMIT_UP_COUNT_10D_WARN:
        return "watch"
    if return_10d_pct is not None and return_10d_pct >= RETURN_10D_WARN_PCT:
        return "watch"
    if return_30d_pct is not None and return_30d_pct >= RETURN_30D_WARN_PCT:
        return "watch"
    return "none"


def _build_summary(
    *,
    limit_up_count_10d: int,
    return_10d_pct: float | None,
    return_30d_pct: float | None,
    risk_level: RiskLevel,
) -> str:
    if risk_level == "none":
        parts: list[str] = []
        if limit_up_count_10d > 0:
            parts.append(f"10 日 {limit_up_count_10d} 涨停")
        if return_30d_pct is not None:
            parts.append(f"30 日 +{return_30d_pct:.0f}%")
        return "；".join(parts) if parts else "暂无异动预警"

    if limit_up_count_10d >= LIMIT_UP_COUNT_10D_THRESHOLD:
        return f"近 10 日 {limit_up_count_10d} 次涨停，已达监管严重异动线（4 次）"
    if limit_up_count_10d >= LIMIT_UP_COUNT_10D_WARN:
        remain = LIMIT_UP_COUNT_10D_THRESHOLD - limit_up_count_10d
        return f"近 10 日 {limit_up_count_10d} 次涨停，距严重异动线还差 {remain} 次"
    if return_10d_pct is not None and return_10d_pct >= RETURN_10D_THRESHOLD_PCT:
        return f"近 10 日涨幅 {return_10d_pct:.0f}%，已达 100% 异动阈值"
    if return_10d_pct is not None and return_10d_pct >= RETURN_10D_WARN_PCT:
        gap = RETURN_10D_THRESHOLD_PCT - return_10d_pct
        return f"近 10 日涨幅 {return_10d_pct:.0f}%，距 100% 异动阈值约 {gap:.0f}%"
    if return_30d_pct is not None and return_30d_pct >= RETURN_30D_THRESHOLD_PCT:
        return f"近 30 日涨幅 {return_30d_pct:.0f}%，已达 200% 严重异动线"
    if return_30d_pct is not None and return_30d_pct >= RETURN_30D_WARN_PCT:
        gap = RETURN_30D_THRESHOLD_PCT - return_30d_pct
        return f"近 30 日涨幅 {return_30d_pct:.0f}%，距 200% 严重异动线约 {gap:.0f}%"
    return "接近监管异动阈值，注意节奏"


def assess_regulatory_deviation(bars: list[BarData]) -> RegulatoryDeviationSnapshot:
    """基于本地日 K 评估监管异动距离。"""
    limit_up_count_10d = _limit_up_count(bars, 10)
    return_10d_pct = _cumulative_return_pct(bars, 10)
    return_30d_pct = _cumulative_return_pct(bars, 30)
    risk_level = _classify_risk(
        limit_up_count_10d=limit_up_count_10d,
        return_10d_pct=return_10d_pct,
        return_30d_pct=return_30d_pct,
    )
    summary = _build_summary(
        limit_up_count_10d=limit_up_count_10d,
        return_10d_pct=return_10d_pct,
        return_30d_pct=return_30d_pct,
        risk_level=risk_level,
    )
    return RegulatoryDeviationSnapshot(
        limit_up_count_10d=limit_up_count_10d,
        return_10d_pct=round(return_10d_pct, 2) if return_10d_pct is not None else None,
        return_30d_pct=round(return_30d_pct, 2) if return_30d_pct is not None else None,
        risk_level=risk_level,
        summary=summary,
    )


def assess_regulatory_deviation_for_symbol(vt_symbol: str) -> dict[str, Any]:
    """按 vt_symbol 加载日 K 并返回监管异动评估（供 AI 工具）。"""
    item = parse_stock_symbol(vt_symbol)
    if item is None:
        return {"error": f"无法解析代码: {vt_symbol}"}

    bars = load_daily_bars_tail(item.symbol, item.exchange, lookback_bars=45)
    if len(bars) < 11:
        return {"error": "本地日 K 不足，请先同步行情数据", "vt_symbol": vt_symbol}
    snapshot = assess_regulatory_deviation(bars)
    return dump_json(snapshot)
