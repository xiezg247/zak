"""选股维度共用的日线历史信号（本地日 K）。"""

from __future__ import annotations

import os
from collections.abc import Sequence
from typing import Any

from vnpy.trader.constant import Exchange
from vnpy.trader.object import BarData

from vnpy_ashare.data.pattern_bars import load_daily_bars_batch
from vnpy_ashare.domain.market.quote_row import QuoteRowLike
from vnpy_ashare.domain.symbols import StockItem, parse_stock_symbol
from vnpy_ashare.screener.data.screening_context_registry import get_screening_context


def history_lookback_bars() -> int:
    raw = os.getenv("SCREENING_HISTORY_LOOKBACK_BARS", "25").strip()
    try:
        return max(10, min(int(raw), 60))
    except ValueError:
        return 25


def load_history_bars_map(vt_symbols: list[str]) -> dict[tuple[str, Exchange], list[BarData]]:

    ctx = get_screening_context()
    if ctx is not None:
        return ctx.load_history_bars_for_symbols(vt_symbols)
    return _load_history_bars_map_uncached(vt_symbols)


def _load_history_bars_map_uncached(vt_symbols: list[str]) -> dict[tuple[str, Exchange], list[BarData]]:
    items: list[StockItem] = []
    seen: set[tuple[str, Exchange]] = set()
    for vt_symbol in vt_symbols:
        item = parse_stock_symbol(vt_symbol)
        if item is None:
            continue
        key = (item.symbol, item.exchange)
        if key in seen:
            continue
        seen.add(key)
        items.append(item)
    if not items:
        return {}
    return load_daily_bars_batch(items, lookback_bars=history_lookback_bars())


def bars_for_vt_symbol(
    vt_symbol: str,
    bars_map: dict[tuple[str, Exchange], list[BarData]],
) -> list[BarData]:
    item = parse_stock_symbol(vt_symbol)
    if item is None:
        return []
    return bars_map.get((item.symbol, item.exchange), [])


def positive_close_streak(bars: list[BarData]) -> int:
    """从最近交易日往前数连续收涨天数。"""
    if len(bars) < 2:
        return 0
    streak = 0
    for index in range(len(bars) - 1, 0, -1):
        prev_close = float(bars[index - 1].close_price or 0)
        close = float(bars[index].close_price or 0)
        if prev_close > 0 and close > prev_close:
            streak += 1
        else:
            break
    return streak


def positive_day_count(bars: list[BarData], *, window: int = 5) -> int:
    """近 window 个交易日内收涨天数（相邻收盘比较）。"""
    if len(bars) < 2:
        return 0
    tail = bars[-window:] if len(bars) >= window else bars
    count = 0
    for index in range(1, len(tail)):
        prev_close = float(tail[index - 1].close_price or 0)
        close = float(tail[index].close_price or 0)
        if prev_close > 0 and close > prev_close:
            count += 1
    return count


def rolling_high_before_last(bars: list[BarData], *, lookback_days: int) -> float | None:
    """最近 lookback_days 根日 K 最高价（不含最后一根）。"""
    if lookback_days <= 0 or len(bars) < lookback_days + 1:
        return None
    window = bars[-(lookback_days + 1) : -1]
    highs = [float(bar.high_price or 0) for bar in window]
    highs = [value for value in highs if value > 0]
    if not highs:
        return None
    return max(highs)


def breaks_rolling_high(last_price: float, rolling_high: float, min_break_pct: float) -> bool:
    if rolling_high <= 0 or last_price <= 0:
        return False
    return last_price >= rolling_high * (1 + min_break_pct / 100)


def attach_momentum_persistence(
    rows: Sequence[QuoteRowLike],
    bars_map: dict[tuple[str, Exchange], list[BarData]],
    *,
    window: int = 5,
) -> None:
    for row in rows:
        if not isinstance(row, dict):
            continue
        vt_symbol = str(row.get("vt_symbol") or "")
        bars = bars_for_vt_symbol(vt_symbol, bars_map)
        if not bars:
            continue
        positive_days = positive_day_count(bars, window=window)
        streak = positive_close_streak(bars)
        row["momentum_positive_days"] = positive_days
        row["momentum_close_streak"] = streak


def momentum_persistence_score_factor(row: dict[str, Any]) -> float:
    positive_days = int(row.get("momentum_positive_days") or 0)
    streak = int(row.get("momentum_close_streak") or 0)
    factor = 1.0
    if positive_days >= 4:
        factor += 0.08
    elif positive_days >= 3:
        factor += 0.04
    if streak >= 3:
        factor += 0.04
    return factor
