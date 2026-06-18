"""监管异动距离评估（Tushare 交易所披露 + 本地日 K 近似）。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field
from vnpy.trader.object import BarData

from vnpy_ashare.data.pattern_bars import load_daily_bars_tail
from vnpy_ashare.domain.market.breadth import LIMIT_UP_PCT
from vnpy_ashare.domain.symbols.stock import parse_stock_symbol
from vnpy_ashare.integrations.tushare.stk_shock import (
    ExchangeRegulatoryRecord,
    load_recent_exchange_regulatory_for_vt_symbol,
    parse_deviation_pct_from_reason,
    summarize_exchange_records,
)
from vnpy_common.domain.base import FrozenModel
from vnpy_common.domain.serialize import dump_json

RiskLevel = Literal["none", "watch", "high"]
DataSource = Literal["local", "tushare", "hybrid"]

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
    data_source: DataSource = Field(default="local", description="数据来源")
    exchange_shock_reason: str | None = Field(default=None, description="交易所披露说明")
    exchange_shock_date: str | None = Field(default=None, description="交易所披露日期 YYYYMMDD")
    exchange_deviation_pct: float | None = Field(default=None, description="从披露文案解析的偏离值 %")
    exchange_high_shock: bool = Field(default=False, description="是否严重异常波动")


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


def _exchange_risk_level(records: tuple[ExchangeRegulatoryRecord, ...]) -> RiskLevel:
    if not records:
        return "none"
    if any(item.shock_type == "high_shock" for item in records):
        return "high"
    return "watch"


def merge_with_exchange_records(
    local: RegulatoryDeviationSnapshot,
    records: tuple[ExchangeRegulatoryRecord, ...],
) -> RegulatoryDeviationSnapshot:
    if not records:
        return local

    latest = records[0]
    exchange_risk = _exchange_risk_level(records)
    risk_rank = {"none": 0, "watch": 1, "high": 2}
    merged_risk: RiskLevel = local.risk_level
    if risk_rank[exchange_risk] > risk_rank[local.risk_level]:
        merged_risk = exchange_risk

    exchange_summary = summarize_exchange_records(records)
    if exchange_risk == "high":
        summary = exchange_summary
    elif local.risk_level == "none":
        summary = exchange_summary
    else:
        summary = f"{exchange_summary}；{local.summary}" if local.summary else exchange_summary

    data_source: DataSource = "hybrid" if local.data_source == "local" and local.summary != "暂无异动预警" else "tushare"
    if local.risk_level != "none" and records:
        data_source = "hybrid"

    return local.model_copy(
        update={
            "risk_level": merged_risk,
            "summary": summary,
            "data_source": data_source,
            "exchange_shock_reason": latest.reason or None,
            "exchange_shock_date": latest.trade_date or None,
            "exchange_deviation_pct": parse_deviation_pct_from_reason(latest.reason),
            "exchange_high_shock": latest.shock_type == "high_shock",
        }
    )


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


def assess_regulatory_deviation_for_vt_symbol(
    vt_symbol: str,
    bars: list[BarData] | None = None,
    *,
    exchange_records: tuple[ExchangeRegulatoryRecord, ...] | None = None,
) -> RegulatoryDeviationSnapshot | None:
    """合并交易所披露与本地日 K；bars 不足时仍可返回 Tushare 披露。"""
    if exchange_records is None:
        exchange_records = load_recent_exchange_regulatory_for_vt_symbol(vt_symbol)

    local: RegulatoryDeviationSnapshot | None = None
    if bars is not None and len(bars) >= 11:
        local = assess_regulatory_deviation(bars)
    elif bars is None:
        item = parse_stock_symbol(vt_symbol)
        if item is not None:
            loaded = load_daily_bars_tail(item.symbol, item.exchange, lookback_bars=45)
            if len(loaded) >= 11:
                local = assess_regulatory_deviation(loaded)

    if local is None:
        if not exchange_records:
            return None
        empty = RegulatoryDeviationSnapshot(summary="暂无异动预警")
        return merge_with_exchange_records(empty, exchange_records)

    return merge_with_exchange_records(local, exchange_records)


def assess_regulatory_deviation_for_symbol(vt_symbol: str) -> dict[str, Any]:
    """按 vt_symbol 加载日 K 并返回监管异动评估（供 AI 工具）。"""
    item = parse_stock_symbol(vt_symbol)
    if item is None:
        return {"error": f"无法解析代码: {vt_symbol}"}

    snapshot = assess_regulatory_deviation_for_vt_symbol(vt_symbol)
    if snapshot is None:
        return {"error": "本地日 K 不足且暂无交易所披露", "vt_symbol": vt_symbol}
    return dump_json(snapshot)
