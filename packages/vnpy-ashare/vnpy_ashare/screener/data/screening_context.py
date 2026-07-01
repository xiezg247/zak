"""选股单次运行内的行情 / 因子缓存（配方并行维度、雷达整板加载共用）。"""

from __future__ import annotations

import os
import threading
from contextlib import contextmanager
from typing import Any

from pydantic import ConfigDict, PrivateAttr
from vnpy.trader.constant import Exchange
from vnpy.trader.object import BarData

from vnpy_ashare.data.download_concurrency import avg_turnover_prefetch_max_workers, run_parallel_map
from vnpy_ashare.data.pattern_bars import load_daily_bars_batch
from vnpy_ashare.domain.symbols.stock import StockItem, parse_stock_symbol
from vnpy_ashare.domain.time.trade_dates import iter_trade_date_strs
from vnpy_ashare.integrations.tushare.factors import (
    fetch_daily_basic,
    fetch_stock_industry_l1_map,
    fetch_stock_industry_map,
)
from vnpy_ashare.screener.data.data_source import load_screening_quote_snapshot_uncached
from vnpy_ashare.screener.data.quote_snapshot_cache import register_cached_quote_snapshot_reader
from vnpy_ashare.screener.data.quotes_loader import MarketQuotesLoadError, MarketQuotesSnapshot
from vnpy_ashare.screener.data.screening_context_registry import (
    activate_screening_context,
    deactivate_screening_context,
    get_screening_context,
)
from vnpy_common.domain.base import MutableModel


def _history_lookback_bars() -> int:
    raw = os.getenv("SCREENING_HISTORY_LOOKBACK_BARS", "25").strip()
    try:
        return max(10, min(int(raw), 60))
    except ValueError:
        return 25


class ScreeningContext(MutableModel):
    """同一次配方 / 雷达刷新内共享的数据快照。"""

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        arbitrary_types_allowed=True,
    )

    _lock: threading.Lock = PrivateAttr(default_factory=threading.Lock)
    _snapshot: MarketQuotesSnapshot | None = PrivateAttr(default=None)
    _snapshot_loaded: bool = PrivateAttr(default=False)
    _snapshot_error: MarketQuotesLoadError | None = PrivateAttr(default=None)
    _volume_ratio_map: dict[str, float] | None = PrivateAttr(default=None)
    _volume_ratio_loaded: bool = PrivateAttr(default=False)
    _avg_turnover_map: dict[str, float] | None = PrivateAttr(default=None)
    _avg_turnover_loaded: bool = PrivateAttr(default=False)
    _industry_map: dict[str, str] | None = PrivateAttr(default=None)
    _industry_map_loaded: bool = PrivateAttr(default=False)
    _industry_l1_map: dict[str, str] | None = PrivateAttr(default=None)
    _industry_l1_map_loaded: bool = PrivateAttr(default=False)
    _history_bars_map: dict[tuple[str, Exchange], list[BarData]] = PrivateAttr(default_factory=dict)
    _snapshot_frame: Any | None = PrivateAttr(default=None)

    def load_history_bars_for_symbols(
        self,
        vt_symbols: list[str],
    ) -> dict[tuple[str, Exchange], list[BarData]]:
        items: list[StockItem] = []
        for vt_symbol in vt_symbols:
            item = parse_stock_symbol(vt_symbol)
            if item is None:
                continue
            key = (item.symbol, item.exchange)
            if key in self._history_bars_map:
                continue
            items.append(item)
        if items:
            loaded = load_daily_bars_batch(items, lookback_bars=_history_lookback_bars())
            with self._lock:
                self._history_bars_map.update(loaded)
        return dict(self._history_bars_map)

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

    def get_quote_snapshot_frame(self) -> Any:
        """Polars 行情 DataFrame（同一次上下文内缓存）。"""
        if self._snapshot_frame is not None:
            return self._snapshot_frame
        from vnpy_ashare.screener.engine.snapshot_frame import snapshot_rows_to_dataframe

        snapshot = self.get_quote_snapshot()
        with self._lock:
            if self._snapshot_frame is None:
                self._snapshot_frame = snapshot_rows_to_dataframe(snapshot.rows)
        return self._snapshot_frame

    def preload_volume_ratio_map(self) -> dict[str, float]:
        return self.get_volume_ratio_map()

    def load_volume_ratio_from_snapshot(self, snapshot: MarketQuotesSnapshot | None) -> None:
        """从行情快照行直接提取 volume_ratio（避免 Tushare daily_basic 请求）。"""
        if self._volume_ratio_loaded or snapshot is None:
            return
        with self._lock:
            if self._volume_ratio_loaded:
                return
            result: dict[str, float] = {}
            for row in snapshot.rows:
                vt = str(getattr(row, "vt_symbol", "") or "")
                vr = float(getattr(row, "volume_ratio", 0) or 0)
                if vt and vr > 0:
                    result[vt] = vr
            self._volume_ratio_map = result
            self._volume_ratio_loaded = True

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
        self.get_industry_l1_map()
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

    def get_industry_l1_map(self) -> dict[str, str]:
        if self._industry_l1_map_loaded:
            return self._industry_l1_map or {}
        with self._lock:
            if not self._industry_l1_map_loaded:
                try:
                    self._industry_l1_map = fetch_stock_industry_l1_map()
                except Exception:
                    self._industry_l1_map = {}
                self._industry_l1_map_loaded = True
        return self._industry_l1_map or {}


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
    trade_dates = list(iter_trade_date_strs(max_lookback=lookback_days))

    def _fetch_day(trade_date: str) -> list[tuple[str, float]]:
        try:
            rows, _ = fetch_daily_basic(trade_date=trade_date)
        except Exception:
            return []
        day_rows: list[tuple[str, float]] = []
        for row in rows:
            vt_symbol = str(row.get("vt_symbol") or "")
            turnover = float(row.get("turnover_rate") or 0)
            if not vt_symbol or turnover <= 0:
                continue
            day_rows.append((vt_symbol, turnover))
        return day_rows

    workers = avg_turnover_prefetch_max_workers(item_count=len(trade_dates))
    day_results = run_parallel_map(trade_dates, _fetch_day, max_workers=workers)
    sums: dict[str, float] = {}
    counts: dict[str, int] = {}
    for day_rows in day_results:
        for vt_symbol, turnover in day_rows:
            sums[vt_symbol] = sums.get(vt_symbol, 0.0) + turnover
            counts[vt_symbol] = counts.get(vt_symbol, 0) + 1
    return {vt_symbol: sums[vt_symbol] / counts[vt_symbol] for vt_symbol in sums if counts.get(vt_symbol, 0) > 0}


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


def get_stock_industry_l1_map() -> dict[str, str]:
    ctx = get_screening_context()
    if ctx is not None:
        return ctx.get_industry_l1_map()
    try:
        return fetch_stock_industry_l1_map()
    except Exception:
        return {}


@contextmanager
def screening_context_scope():
    """进入配方 / 雷达批量加载作用域，子线程通过 copy_context 继承。"""
    ctx = ScreeningContext()
    token = activate_screening_context(ctx)
    try:
        yield ctx
    finally:
        deactivate_screening_context(token)


def preload_screening_context(ctx: ScreeningContext) -> None:
    """预加载常用字段，避免并行维度重复拉 Redis / Tushare。"""
    ctx.preload_quote_snapshot()
    _coarse_prefilter_snapshot(ctx)
    _prefilter_snapshot(ctx)
    ctx.load_volume_ratio_from_snapshot(
        getattr(ctx, "_snapshot", None)
    )
    ctx.preload_avg_turnover_map()
    ctx.preload_industry_map()
    try:
        ctx.get_quote_snapshot_frame()
    except Exception:
        pass


def _coarse_prefilter_snapshot(ctx: ScreeningContext) -> None:
    """粗筛：仅用行情快照字段（零 API 调用）先过滤无效/涨跌停/低流动性/北交所标的。
    
    在硬过滤和 Tushare 重请求之前执行，显著减少后续处理行数。
    """
    snapshot = getattr(ctx, "_snapshot", None)
    if snapshot is None or not getattr(snapshot, "rows", None):
        return
    rows = list(snapshot.rows)
    original = len(rows)
    filtered = _apply_coarse_quote_filters(rows)
    if len(filtered) == original:
        return

    from vnpy_ashare.screener.data.quotes_loader import MarketQuotesSnapshot
    from vnpy_ashare.domain.market.quote_row import coerce_quote_rows

    ctx._snapshot = MarketQuotesSnapshot(
        rows=coerce_quote_rows(filtered),
        updated_at=snapshot.updated_at,
        total=len(filtered),
        source=snapshot.source,
    )


def _apply_coarse_quote_filters(rows: list) -> list:
    """纯行内字段过滤，不发起任何外部请求。"""
    from vnpy_ashare.screener.hard_filters import recipe_min_amount_yuan

    min_amount = recipe_min_amount_yuan()
    kept: list = []
    for row in rows:
        last_price = float(row.get("last_price") or 0)
        if last_price <= 0:
            continue

        # 涨跌停排除
        change_pct = float(row.get("change_pct") or 0)
        symbol = str(row.get("symbol") or "")
        if _at_any_limit_board(symbol, change_pct):
            continue

        # 流动性：成交额过低
        if min_amount > 0:
            amount = float(row.get("amount") or 0)
            if amount < min_amount:
                continue

        # 北交所排除
        if _is_beijing_board(symbol):
            continue

        kept.append(row)
    return kept


def _at_any_limit_board(symbol: str, change_pct: float) -> bool:
    """涨跌停或接近涨跌停（主板 ±9.8%，科创/创业板 ±19.5%）。"""
    if symbol.startswith(("300", "688")):
        return abs(change_pct) >= 19.5
    return abs(change_pct) >= 9.8


def _is_beijing_board(symbol: str) -> bool:
    """北交所主板（4/8开头）。"""
    return bool(symbol) and symbol[0] in ("4", "8")


def _prefilter_snapshot(ctx: ScreeningContext) -> None:
    """提前应用硬过滤（ST、停牌、流动性），减少后续维度和 DataFrame 规模。"""
    from vnpy_ashare.screener.data.screening_sentiment_prefilter import apply_recipe_prefilter_to_context

    apply_recipe_prefilter_to_context(ctx)


def preload_screening_context_quotes(ctx: ScreeningContext) -> None:
    """仅预加载行情快照（选股 / 展望卡补现价用）。"""
    ctx.preload_quote_snapshot()


register_cached_quote_snapshot_reader(get_cached_quote_snapshot)
