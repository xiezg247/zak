"""策略信号相对大盘基准（沪深300）。"""

from __future__ import annotations

from typing import Any, Protocol

from vnpy.trader.constant import Exchange

from vnpy_ashare.integrations.tushare.factors import fetch_index_daily_snapshot

SIGNAL_BENCHMARK_SYMBOL = "000300"
SIGNAL_BENCHMARK_LOOKBACK = 20
SIGNAL_BENCHMARK_TS_CODE = "000300.SH"


class BarReturnReader(Protocol):
    def get_return(
        self,
        symbol: str,
        exchange: Exchange,
        scope: str = "daily",
        lookback_days: int = 20,
    ) -> dict[str, Any]: ...


def benchmark_return_from_index_rows(
    rows: list[dict[str, Any]],
    *,
    lookback: int = SIGNAL_BENCHMARK_LOOKBACK,
    ts_code: str = SIGNAL_BENCHMARK_TS_CODE,
) -> float | None:
    """从 index_daily 行列表计算区间涨幅（%）。"""
    target = ts_code.strip().upper()
    points = [row for row in rows if str(row.get("ts_code", "")).strip().upper() == target and row.get("close") is not None]
    if len(points) < 2:
        return None
    points.sort(key=lambda row: str(row.get("trade_date", "")))
    closes = [float(row["close"]) for row in points]
    tail = closes[-lookback:] if len(closes) >= lookback else closes
    first = tail[0]
    last = tail[-1]
    if first <= 0:
        return None
    return round((last - first) / first * 100, 2)


def benchmark_return_from_tushare_cache(
    *,
    lookback: int = SIGNAL_BENCHMARK_LOOKBACK,
    ts_code: str = SIGNAL_BENCHMARK_TS_CODE,
) -> float | None:
    """读取 Tushare index_daily 本地缓存（必要时拉取一次）。"""

    try:
        rows, _trade_date = fetch_index_daily_snapshot()
    except Exception:
        return None
    if not rows:
        return None
    return benchmark_return_from_index_rows(rows, lookback=lookback, ts_code=ts_code)


def resolve_benchmark_return_pct(
    bar_service: BarReturnReader,
    *,
    lookback: int = SIGNAL_BENCHMARK_LOOKBACK,
) -> float | None:
    """优先本地 000300 日 K，缺失时回退 Tushare index_daily 缓存。"""
    result = bar_service.get_return(
        SIGNAL_BENCHMARK_SYMBOL,
        Exchange.SSE,
        lookback_days=lookback,
    )
    pct = result.get("return_pct")
    if isinstance(pct, (int, float)):
        return float(pct)
    return benchmark_return_from_tushare_cache(lookback=lookback)


def compute_relative_index_excess(
    bar_service: BarReturnReader,
    symbol: str,
    exchange: Exchange,
    *,
    lookback: int = SIGNAL_BENCHMARK_LOOKBACK,
    benchmark_pct: float | None = None,
) -> float | None:
    """个股区间涨幅减基准涨幅（百分点）。"""
    stock = bar_service.get_return(symbol, exchange, lookback_days=lookback)
    stock_pct = stock.get("return_pct")
    bench_pct = benchmark_pct
    if bench_pct is None:
        bench_pct = resolve_benchmark_return_pct(bar_service, lookback=lookback)
    if not isinstance(stock_pct, (int, float)) or bench_pct is None:
        return None
    return round(float(stock_pct) - bench_pct, 2)
