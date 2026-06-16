"""自选多维看盘迷你图数据（日 K / 分时）。"""

from __future__ import annotations

from typing import Literal

from vnpy.trader.object import BarData

from vnpy_ashare.data.download_concurrency import run_parallel_map
from vnpy_ashare.data.pattern_bars import load_daily_bars_batch
from vnpy_ashare.domain.market_hours import is_ashare_trading_session
from vnpy_ashare.domain.symbols import StockItem
from vnpy_ashare.integrations.tickflow.klines import fetch_intraday_bars

SparklineKind = Literal["daily", "intraday", "none"]
SPARKLINE_DAILY_BARS = 24
SPARKLINE_INTRADAY_MAX_POINTS = 48
SPARKLINE_INTRADAY_MAX_WORKERS = 4


def _downsample_closes(closes: list[float], *, max_points: int) -> tuple[float, ...]:
    if len(closes) <= max_points:
        return tuple(closes)
    if max_points < 2:
        return tuple(closes[:max_points])
    step = (len(closes) - 1) / (max_points - 1)
    indices = {min(len(closes) - 1, int(round(index * step))) for index in range(max_points)}
    ordered = sorted(indices)
    return tuple(closes[index] for index in ordered)


def closes_from_bars(bars: list[BarData], *, max_points: int) -> tuple[float, ...]:
    closes = [float(bar.close_price) for bar in bars if bar.close_price and float(bar.close_price) > 0]
    if len(closes) < 2:
        return ()
    return _downsample_closes(closes, max_points=max_points)


def load_daily_sparklines(items: list[StockItem]) -> dict[str, tuple[float, ...]]:
    if not items:
        return {}
    loaded = load_daily_bars_batch(items, lookback_bars=SPARKLINE_DAILY_BARS)
    result: dict[str, tuple[float, ...]] = {}
    for item in items:
        bars = loaded.get((item.symbol, item.exchange), [])
        points = closes_from_bars(bars, max_points=SPARKLINE_DAILY_BARS)
        if points:
            result[item.vt_symbol] = points
    return result


def _load_intraday_entry(item: StockItem) -> tuple[str, tuple[float, ...]]:
    try:
        bars = fetch_intraday_bars(item)
        points = closes_from_bars(bars, max_points=SPARKLINE_INTRADAY_MAX_POINTS)
        return item.vt_symbol, points
    except Exception:
        return item.vt_symbol, ()


def load_intraday_sparklines(items: list[StockItem]) -> dict[str, tuple[float, ...]]:
    if not items:
        return {}
    workers = min(SPARKLINE_INTRADAY_MAX_WORKERS, len(items))
    if workers <= 1:
        pairs = [_load_intraday_entry(item) for item in items]
    else:
        pairs = run_parallel_map(items, _load_intraday_entry, max_workers=workers)
    return {vt_symbol: points for vt_symbol, points in pairs if points}


def load_watchlist_sparklines(items: list[StockItem]) -> tuple[SparklineKind, dict[str, tuple[float, ...]]]:
    if not items:
        return "none", {}
    if is_ashare_trading_session():
        intraday = load_intraday_sparklines(items)
        if intraday:
            return "intraday", intraday
    daily = load_daily_sparklines(items)
    if daily:
        return "daily", daily
    return "none", {}
