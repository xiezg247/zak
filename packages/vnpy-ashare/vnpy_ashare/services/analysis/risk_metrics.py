"""风险指标：Beta、对齐日收益等。"""

from __future__ import annotations

from typing import Any

from vnpy.trader.constant import Exchange

from vnpy_ashare.domain.signal_benchmark import SIGNAL_BENCHMARK_SYMBOL
from vnpy_ashare.screener.sentiment.sentiment_gate import try_fetch_fear_greed_index


def _bar_close_map(bars: list[Any]) -> dict[Any, float]:
    mapping: dict[Any, float] = {}
    for bar in bars:
        dt = getattr(bar, "datetime", None)
        close = getattr(bar, "close_price", None)
        if dt is None or close is None:
            continue
        day = dt.date() if hasattr(dt, "date") else dt
        mapping[day] = float(close)
    return mapping


def _returns_from_closes(closes: list[float]) -> list[float]:
    values: list[float] = []
    for index in range(1, len(closes)):
        prev = closes[index - 1]
        if prev:
            values.append((closes[index] - prev) / prev)
    return values


def compute_beta_vs_hs300(
    stock_bars: list[Any],
    benchmark_bars: list[Any],
    *,
    lookback: int = 60,
) -> float | None:
    """基于对齐日收益计算相对沪深300的 Beta。"""
    stock_map = _bar_close_map(stock_bars)
    bench_map = _bar_close_map(benchmark_bars)
    dates = sorted(set(stock_map.keys()) & set(bench_map.keys()))
    if len(dates) < 10:
        return None
    tail = dates[-(lookback + 1) :]
    stock_closes = [stock_map[day] for day in tail]
    bench_closes = [bench_map[day] for day in tail]
    stock_ret = _returns_from_closes(stock_closes)
    bench_ret = _returns_from_closes(bench_closes)
    if len(stock_ret) < 8 or len(stock_ret) != len(bench_ret):
        return None

    bench_mean = sum(bench_ret) / len(bench_ret)
    stock_mean = sum(stock_ret) / len(stock_ret)
    cov = sum((stock_ret[i] - stock_mean) * (bench_ret[i] - bench_mean) for i in range(len(stock_ret)))
    var = sum((value - bench_mean) ** 2 for value in bench_ret)
    if var <= 0:
        return None
    return round(cov / var, 3)


def fetch_market_sentiment() -> dict[str, Any] | None:
    try:

        snapshot = try_fetch_fear_greed_index()
    except Exception:
        return None
    if snapshot is None:
        return None
    return {
        "fear_greed_index": round(float(snapshot.index), 1),
        "fear_greed_label": snapshot.label,
        "trade_date": getattr(snapshot, "trade_date", "") or "",
    }


def benchmark_symbol_exchange() -> tuple[str, Exchange]:
    return SIGNAL_BENCHMARK_SYMBOL, Exchange.SSE
