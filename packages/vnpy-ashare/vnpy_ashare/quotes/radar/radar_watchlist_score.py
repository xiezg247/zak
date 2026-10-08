"""自选雷达：异动评分、指标与行构建。"""

from __future__ import annotations

from typing import Any

from vnpy_ashare.domain.market.quote_row import QuoteRowLike
from vnpy_ashare.domain.symbols.stock import parse_stock_symbol
from vnpy_ashare.quotes.format import format_amount, format_pct
from vnpy_ashare.quotes.radar.radar_models import RadarRow
from vnpy_ashare.quotes.radar.radar_moneyflow import moneyflow_score_boost, watchlist_moneyflow_metric
from vnpy_ashare.quotes.radar.radar_quotes import merge_row_quotes

__all__ = [
    "SIGNAL_TRANSITION_BOOST",
    "intraday_score",
    "row_from_quote",
    "score_candidates",
    "watchlist_metric",
]

SIGNAL_TRANSITION_BOOST = 35.0


def intraday_score(
    row: QuoteRowLike,
    *,
    transition: str | None = None,
    pool_median_change: float | None = None,
) -> float:
    merged = merge_row_quotes(row)
    change = float(merged.get("change_pct") or 0)
    change_abs = abs(change)
    volume_ratio = float(merged.get("volume_ratio") or 0)
    amount = float(merged.get("amount") or 0)
    turnover = float(merged.get("turnover_rate") or 0)
    score = change_abs * 10.0
    if pool_median_change is not None and change > pool_median_change + 1.0:
        score += (change - pool_median_change) * 6.0
    if volume_ratio >= 1.2:
        score += min(volume_ratio, 5.0) * 4.0
    if amount > 0:
        score += min(amount / 1_000_000_000, 5.0) * 2.0
    if turnover >= 3.0:
        score += min(turnover, 15.0)
    if transition:
        score += SIGNAL_TRANSITION_BOOST
    score += moneyflow_score_boost(row)
    return score


def watchlist_metric(
    row: QuoteRowLike,
    *,
    transition: str | None = None,
) -> tuple[str, str, str, str]:
    if transition:
        merged = merge_row_quotes(row)
        change = float(merged.get("change_pct") or 0)
        return "信号跃迁", transition, "涨幅", format_pct(change)

    mf = watchlist_moneyflow_metric(row)
    if mf is not None:
        return mf

    merged = merge_row_quotes(row)
    change = float(merged.get("change_pct") or 0)
    volume_ratio = float(merged.get("volume_ratio") or 0)
    amount = float(merged.get("amount") or 0)
    turnover = float(merged.get("turnover_rate") or 0)
    if abs(change) >= 2.0:
        return "涨幅", format_pct(change), "量比", f"{volume_ratio:.2f}" if volume_ratio > 0 else "—"
    if volume_ratio >= 1.3:
        return "量比", f"{volume_ratio:.2f}", "涨幅", format_pct(change)
    if amount > 0:
        return "成交额", format_amount(amount), "涨幅", format_pct(change)
    return "换手", f"{turnover:.2f}%" if turnover > 0 else "—", "涨幅", format_pct(change)


def row_from_quote(
    vt_symbol: str,
    row: QuoteRowLike,
    *,
    name_map: dict[str, str],
    transition: str | None = None,
    scenario_hint: str | None = None,
) -> RadarRow | None:
    item = parse_stock_symbol(vt_symbol)
    if item is None:
        return None
    merged = merge_row_quotes(row)
    name = str(merged.get("name") or name_map.get(vt_symbol) or item.name or vt_symbol)
    price_raw = merged.get("last_price") or merged.get("close")
    price = float(price_raw) if isinstance(price_raw, (int, float)) and float(price_raw) > 0 else None
    change_raw = merged.get("change_pct")
    change_pct = float(change_raw) if isinstance(change_raw, (int, float)) else None
    metric_label, metric_value, sub_label, sub_value = watchlist_metric(merged, transition=transition)
    if scenario_hint:
        sub_label = "5日情景"
        sub_value = scenario_hint
    return RadarRow(
        vt_symbol=vt_symbol,
        name=name,
        symbol=item.symbol,
        price=price,
        change_pct=change_pct,
        metric_label=metric_label,
        metric_value=metric_value,
        sub_label=sub_label,
        sub_value=sub_value,
    )


def score_candidates(
    candidates: list[str],
    quotes_by_vt: dict[str, dict[str, Any]],
    transitions: dict[str, str],
    *,
    anomaly_only: bool,
) -> list[tuple[str, dict[str, Any], float, str | None]]:
    changes = [
        float(merge_row_quotes(quotes_by_vt.get(vt, {})).get("change_pct") or 0)
        for vt in candidates
        if quotes_by_vt.get(vt)
    ]
    pool_median = sorted(changes)[len(changes) // 2] if changes else 0.0

    scored: list[tuple[str, dict[str, Any], float, str | None]] = []
    for vt_symbol in candidates:
        row = quotes_by_vt.get(vt_symbol, {"vt_symbol": vt_symbol})
        transition = transitions.get(vt_symbol)
        score = intraday_score(row, transition=transition, pool_median_change=pool_median)
        merged = merge_row_quotes(row)
        change = abs(float(merged.get("change_pct") or 0))
        rel_change = float(merged.get("change_pct") or 0) - pool_median
        volume_ratio = float(merged.get("volume_ratio") or 0)
        if transition:
            scored.append((vt_symbol, row, score, transition))
            continue
        if not anomaly_only:
            scored.append((vt_symbol, row, score, None))
            continue
        if change < 1.5 and volume_ratio < 1.2 and score < 8.0 and rel_change < 1.0:
            net_mf = float(merge_row_quotes(row).get("net_mf_amount") or 0)
            if net_mf <= 0:
                continue
        scored.append((vt_symbol, row, score, None))
    scored.sort(key=lambda item: item[2], reverse=True)
    return scored
