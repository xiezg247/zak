"""形态选股专用日 K 加载（尾部窗口，避免全量扫库）。"""

from __future__ import annotations

from datetime import timedelta

from vnpy.trader.constant import Exchange
from vnpy.trader.object import BarData

from vnpy_ashare.data.bar_store import get_scope_overview, load_scope_bars
from vnpy_ashare.domain.models import StockItem

PATTERN_MIN_BARS = 60
PATTERN_LOOKBACK_BARS = 120


def load_daily_bars_tail(
    symbol: str,
    exchange: Exchange,
    *,
    lookback_bars: int = PATTERN_LOOKBACK_BARS,
) -> list[BarData]:
    """按 overview 尾部加载日 K，供形态规则使用。"""
    overview = get_scope_overview(symbol, exchange, "daily")
    if overview is None:
        return []

    end = overview.end
    calendar_days = int(lookback_bars * 1.6) + 10
    start = end - timedelta(days=calendar_days)
    if start < overview.start:
        start = overview.start

    bars = load_scope_bars(symbol, exchange, "daily", start, end)
    if len(bars) > lookback_bars:
        return bars[-lookback_bars:]
    return bars


def load_daily_bars_batch(
    items: list[StockItem],
    *,
    lookback_bars: int = PATTERN_LOOKBACK_BARS,
) -> dict[tuple[str, Exchange], list[BarData]]:
    """批量加载形态选股所需日 K（每标的独立尾部窗口）。"""
    result: dict[tuple[str, Exchange], list[BarData]] = {}
    for item in items:
        key = (item.symbol, item.exchange)
        if key in result:
            continue
        result[key] = load_daily_bars_tail(item.symbol, item.exchange, lookback_bars=lookback_bars)
    return result
