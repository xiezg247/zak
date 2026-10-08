"""雷达展望：全市场粗筛与日 K 就绪集合。"""

from __future__ import annotations

import time

from vnpy_ashare.config.preferences.watchlist_signal import WatchlistSignalConfig
from vnpy_ashare.data.bar_access import iter_bar_overviews
from vnpy_ashare.domain.radar.horizon import HorizonScanStats
from vnpy_ashare.domain.symbols.stock import StockItem
from vnpy_ashare.quotes.radar.outlook_strategy_prefs import load_outlook_signal_config
from vnpy_ashare.screener.data.data_source import load_screening_quote_snapshot
from vnpy_ashare.screener.data.quotes_loader import MarketQuotesLoadError
from vnpy_ashare.screener.engine.frame import row_to_dict
from vnpy_ashare.screener.hard_filters import apply_recipe_filters

__all__ = [
    "HORIZON_PREFILTER_TOP",
    "collect_daily_k_ready_vt_symbols",
    "horizon_empty_message",
    "horizon_min_signal_bars",
    "local_daily_k_insufficient",
    "prefilter_horizon_universe",
]

HORIZON_PREFILTER_TOP = 200
_DAILY_K_READY_TTL_SEC = 60.0
_daily_k_ready_cache: tuple[int, float, set[str]] | None = None


def horizon_min_signal_bars(config: WatchlistSignalConfig | None = None) -> int:
    cfg = (config or load_outlook_signal_config()).normalized()
    return cfg.slow_window + 5


def collect_daily_k_ready_vt_symbols(
    min_bars: int | None = None,
    *,
    config: WatchlistSignalConfig | None = None,
) -> set[str]:
    """本地日 K 条数达信号计算下限的 vt_symbol 集合（用 overview 粗判，避免全量 load）。"""
    global _daily_k_ready_cache
    required = int(min_bars or horizon_min_signal_bars(config))
    now = time.monotonic()
    if _daily_k_ready_cache is not None:
        cached_required, cached_at, cached_ready = _daily_k_ready_cache
        if cached_required == required and now - cached_at < _DAILY_K_READY_TTL_SEC:
            return set(cached_ready)

    ready: set[str] = set()
    for row in iter_bar_overviews(scope="daily"):
        if int(row.count or 0) >= required:
            ready.add(StockItem(symbol=row.symbol, exchange=row.exchange).vt_symbol)
    _daily_k_ready_cache = (required, now, ready)
    return ready


def local_daily_k_insufficient(stats: HorizonScanStats) -> bool:
    """粗筛池内过半无法算信号时视为本地日 K 覆盖不足。"""
    if stats.prefilter_total <= 0:
        return False
    if stats.refined_total > 0:
        return False
    return stats.kline_missing >= max(1, stats.prefilter_total // 2)


def horizon_empty_message(stats: HorizonScanStats, *, card_title: str) -> str:
    if stats.prefilter_total == 0 and stats.scanned_total == 0:
        return "暂无全市场行情，请先同步标的或等待行情采集。"
    if stats.prefilter_total == 0:
        if not collect_daily_k_ready_vt_symbols():
            return "本地暂无日 K 数据，请先运行「全市场日 K」或「补全本地日 K」。"
        return "粗筛池为空（行情硬过滤后无候选，或标的均在排除清单中），请稍后重试。"
    if local_daily_k_insufficient(stats):
        return (
            f"本地日 K 覆盖不足，请先运行「全市场日 K」或「补全本地日 K」"
            f"（粗筛 {stats.prefilter_total} 只，可算信号 0 只）。"
        )
    return f"当前无符合「{card_title}」条件的标的（已扫描 {stats.scanned_total} 只）。"


def prefilter_horizon_universe(
    exclusion: set[str],
    *,
    max_items: int = HORIZON_PREFILTER_TOP,
    config: WatchlistSignalConfig | None = None,
) -> tuple[list[str], HorizonScanStats]:
    """行情粗筛：硬过滤 + 排除自选/信号区/持仓 + 仅保留本地日 K 达标 + 流动性 Top N。"""
    try:
        snapshot = load_screening_quote_snapshot()
    except MarketQuotesLoadError:
        return [], HorizonScanStats(
            scanned_total=0,
            excluded_count=len(exclusion),
            prefilter_total=0,
            refined_total=0,
            kline_missing=0,
        )

    scanned_total = int(snapshot.total or len(snapshot.rows))
    filtered = apply_recipe_filters(list(snapshot.rows))
    min_bars = horizon_min_signal_bars(config)
    k_ready = collect_daily_k_ready_vt_symbols(min_bars, config=config)

    import polars as pl

    # Polars 向量化：排除 + 日K达标 + 流动性排序
    payloads = [row_to_dict(row) for row in filtered]
    df = pl.DataFrame(payloads, infer_schema_length=max(len(payloads), 1))
    if "vt_symbol" not in df.columns:
        return [], HorizonScanStats(
            scanned_total=scanned_total,
            excluded_count=len(exclusion),
            prefilter_total=0,
            refined_total=0,
            kline_missing=0,
        )

    vt_col = pl.col("vt_symbol").cast(pl.Utf8, strict=False).fill_null("")
    df = df.filter(
        vt_col.str.len_chars() > 0,
        ~vt_col.is_in(list(exclusion)),
        vt_col.is_in(list(k_ready)),
    )
    if df.is_empty():
        return [], HorizonScanStats(
            scanned_total=scanned_total,
            excluded_count=len(exclusion),
            prefilter_total=0,
            refined_total=0,
            kline_missing=0,
        )

    # 交易时段 Redis 行情可能缺少 total_mv/circ_mv/turnover_rate 等字段
    for col_name in ("volume", "amount", "total_mv", "circ_mv", "turnover_rate"):
        if col_name not in df.columns:
            df = df.with_columns(pl.lit(None).alias(col_name))

    liq = pl.max_horizontal(
        pl.col("volume").cast(pl.Float64, strict=False).fill_null(0.0),
        pl.col("amount").cast(pl.Float64, strict=False).fill_null(0.0),
        pl.col("total_mv").cast(pl.Float64, strict=False).fill_null(0.0),
        pl.col("circ_mv").cast(pl.Float64, strict=False).fill_null(0.0),
        pl.col("turnover_rate").cast(pl.Float64, strict=False).fill_null(0.0),
    ).alias("_liq")
    ranked = df.with_columns(liq).sort("_liq", descending=True, nulls_last=True)
    cap = max(1, min(int(max_items), HORIZON_PREFILTER_TOP))
    prefilter = ranked.head(cap).select(vt_col).to_series().to_list()
    prefilter = [vt for vt in prefilter if vt]
    return prefilter, HorizonScanStats(
        scanned_total=scanned_total,
        excluded_count=len(exclusion),
        prefilter_total=len(prefilter),
        refined_total=0,
        kline_missing=0,
    )
