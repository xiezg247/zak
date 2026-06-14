"""选股单次运行内的行情 / 因子缓存（配方并行维度、雷达整板加载共用）。"""

from __future__ import annotations

import threading
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field

from vnpy_ashare.integrations.tushare.factors import fetch_daily_basic, fetch_stock_industry_map
from vnpy_ashare.screener.data.data_source import iter_trade_date_strs
from vnpy_ashare.screener.data.quotes_loader import MarketQuotesLoadError, MarketQuotesSnapshot

_screening_ctx: ContextVar[ScreeningContext | None] = ContextVar("screening_ctx", default=None)


@dataclass
class ScreeningContext:
    """同一次配方 / 雷达刷新内共享的数据快照。"""

    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _snapshot: MarketQuotesSnapshot | None = None
    _snapshot_loaded: bool = False
    _snapshot_error: MarketQuotesLoadError | None = None
    _volume_ratio_map: dict[str, float] | None = None
    _volume_ratio_loaded: bool = False
    _avg_turnover_map: dict[str, float] | None = None
    _avg_turnover_loaded: bool = False
    _industry_map: dict[str, str] | None = None
    _industry_map_loaded: bool = False

    def preload_quote_snapshot(self) -> MarketQuotesSnapshot | None:
        """预加载行情；失败时记录错误供后续维度降级。"""
        try:
            return self.get_quote_snapshot()
        except MarketQuotesLoadError as exc:
            self._snapshot_error = exc
            return None

    def get_quote_snapshot(self) -> MarketQuotesSnapshot:
        if self._snapshot_loaded:
            if self._snapshot_error is not None:
                raise self._snapshot_error
            if self._snapshot is None:
                raise MarketQuotesLoadError("行情快照不可用。")
            return self._snapshot
        with self._lock:
            if not self._snapshot_loaded:
                from vnpy_ashare.screener.data.data_source import load_screening_quote_snapshot_uncached

                try:
                    self._snapshot = load_screening_quote_snapshot_uncached()
                except MarketQuotesLoadError as exc:
                    self._snapshot_error = exc
                self._snapshot_loaded = True
        if self._snapshot_error is not None:
            raise self._snapshot_error
        if self._snapshot is None:
            raise MarketQuotesLoadError("行情快照不可用。")
        return self._snapshot

    def preload_volume_ratio_map(self) -> dict[str, float]:
        return self.get_volume_ratio_map()

    def get_volume_ratio_map(self) -> dict[str, float]:
        if self._volume_ratio_loaded:
            return self._volume_ratio_map or {}
        with self._lock:
            if not self._volume_ratio_loaded:
                self._volume_ratio_map = fetch_volume_ratio_map_uncached()
                self._volume_ratio_loaded = True
        return self._volume_ratio_map or {}

    def preload_avg_turnover_map(self) -> dict[str, float]:
        return self.get_avg_turnover_map()

    def get_avg_turnover_map(self) -> dict[str, float]:
        if self._avg_turnover_loaded:
            return self._avg_turnover_map or {}
        with self._lock:
            if not self._avg_turnover_loaded:
                self._avg_turnover_map = fetch_avg_turnover_map_uncached()
                self._avg_turnover_loaded = True
        return self._avg_turnover_map or {}

    def preload_industry_map(self) -> dict[str, str]:
        return self.get_industry_map()

    def get_industry_map(self) -> dict[str, str]:
        if self._industry_map_loaded:
            return self._industry_map or {}
        with self._lock:
            if not self._industry_map_loaded:
                try:
                    self._industry_map = fetch_stock_industry_map()
                except Exception:
                    self._industry_map = {}
                self._industry_map_loaded = True
        return self._industry_map or {}


def get_screening_context() -> ScreeningContext | None:
    return _screening_ctx.get()


def get_cached_quote_snapshot() -> MarketQuotesSnapshot | None:
    """有活跃上下文时返回缓存快照；无上下文或尚未加载时返回 None。"""
    ctx = get_screening_context()
    if ctx is None or not ctx._snapshot_loaded:
        return None
    if ctx._snapshot_error is not None or ctx._snapshot is None:
        return None
    return ctx._snapshot


def fetch_volume_ratio_map_uncached() -> dict[str, float]:
    try:
        basic_rows, _ = fetch_daily_basic()
    except Exception:
        return {}
    return {
        str(row.get("vt_symbol") or ""): float(row.get("volume_ratio") or 0)
        for row in basic_rows
        if row.get("vt_symbol") and float(row.get("volume_ratio") or 0) > 0
    }


def get_volume_ratio_map() -> dict[str, float]:
    ctx = get_screening_context()
    if ctx is not None:
        return ctx.get_volume_ratio_map()
    return fetch_volume_ratio_map_uncached()


def fetch_avg_turnover_map_uncached(*, lookback_days: int = 5) -> dict[str, float]:
    sums: dict[str, float] = {}
    counts: dict[str, int] = {}
    for trade_date in iter_trade_date_strs(max_lookback=lookback_days):
        try:
            rows, _ = fetch_daily_basic(trade_date=trade_date)
        except Exception:
            continue
        if not rows:
            continue
        for row in rows:
            vt_symbol = str(row.get("vt_symbol") or "")
            turnover = float(row.get("turnover_rate") or 0)
            if not vt_symbol or turnover <= 0:
                continue
            sums[vt_symbol] = sums.get(vt_symbol, 0.0) + turnover
            counts[vt_symbol] = counts.get(vt_symbol, 0) + 1
    return {
        vt_symbol: sums[vt_symbol] / counts[vt_symbol]
        for vt_symbol in sums
        if counts.get(vt_symbol, 0) > 0
    }


def get_avg_turnover_map() -> dict[str, float]:
    ctx = get_screening_context()
    if ctx is not None:
        return ctx.get_avg_turnover_map()
    return fetch_avg_turnover_map_uncached()


def get_stock_industry_map() -> dict[str, str]:
    ctx = get_screening_context()
    if ctx is not None:
        return ctx.get_industry_map()
    try:
        return fetch_stock_industry_map()
    except Exception:
        return {}


@contextmanager
def screening_context_scope():
    """进入配方 / 雷达批量加载作用域，子线程通过 copy_context 继承。"""
    ctx = ScreeningContext()
    token = _screening_ctx.set(ctx)
    try:
        yield ctx
    finally:
        _screening_ctx.reset(token)


def preload_screening_context(ctx: ScreeningContext) -> None:
    """预加载常用字段，避免并行维度重复拉 Redis / Tushare。"""
    ctx.preload_quote_snapshot()
    ctx.preload_volume_ratio_map()
    ctx.preload_avg_turnover_map()
    ctx.preload_industry_map()


def preload_screening_context_quotes(ctx: ScreeningContext) -> None:
    """仅预加载行情快照（选股 / 展望卡补现价用）。"""
    ctx.preload_quote_snapshot()
