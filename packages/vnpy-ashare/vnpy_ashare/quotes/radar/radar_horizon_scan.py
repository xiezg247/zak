"""雷达页未来展望全市场扫描（粗筛 + 策略信号精算）。"""

from __future__ import annotations

from typing import Any

from vnpy_ashare.config.preferences.watchlist_signal import WatchlistSignalConfig
from vnpy_ashare.data.bar_access import iter_bar_overviews
from vnpy_ashare.data.download_concurrency import run_parallel_map
from vnpy_ashare.data.pattern_bars import pattern_load_max_workers
from vnpy_ashare.domain.market.quote_row import coerce_quote_row
from vnpy_ashare.domain.radar.horizon import HorizonScanResult
from vnpy_ashare.domain.symbols.stock import StockItem
from vnpy_ashare.domain.time.china import format_china_datetime_minute
from vnpy_ashare.domain.trading.signal_snapshot import SignalSnapshot, signal_missing_kline
from vnpy_ashare.quotes.radar.outlook_strategy_prefs import load_outlook_signal_config
from vnpy_ashare.quotes.radar.radar_horizon_cache import HorizonCacheEntry, put_horizon_cache
from vnpy_ashare.quotes.radar.radar_horizon_rules import (
    build_outlook_rows,
    filter_avoid_snapshots,
    filter_outlook_snapshots,
    outlook_sort_key,
)
from vnpy_ashare.quotes.radar.radar_horizon_scenario import (
    SCENARIO_VARIANTS,
    batch_build_scenario_metrics,
    build_scenario_rows,
    classify_scenario_hint,
    filter_scenario_metrics,
    scenario_sort_key,
)
from vnpy_ashare.quotes.radar.radar_horizon_stats import HorizonScanStats
from vnpy_ashare.quotes.radar.radar_pool import collect_outlook_exclusion_vt_symbols, name_map_for_symbols
from vnpy_ashare.screener.data.data_source import load_screening_quote_snapshot
from vnpy_ashare.screener.data.quotes_loader import MarketQuotesLoadError
from vnpy_ashare.screener.hard_filters import apply_screening_filters
from vnpy_ashare.screener.preset.rules import _quote_liquidity_key

HORIZON_PREFILTER_TOP = 600


def horizon_min_signal_bars(config: WatchlistSignalConfig | None = None) -> int:
    cfg = (config or load_outlook_signal_config()).normalized()
    return cfg.slow_window + 5


def collect_daily_k_ready_vt_symbols(
    min_bars: int | None = None,
    *,
    config: WatchlistSignalConfig | None = None,
) -> set[str]:
    """本地日 K 条数达信号计算下限的 vt_symbol 集合（用 overview 粗判，避免全量 load）。"""
    required = int(min_bars or horizon_min_signal_bars(config))

    ready: set[str] = set()
    for row in iter_bar_overviews(scope="daily"):
        if int(row.count or 0) >= required:
            ready.add(StockItem(symbol=row.symbol, exchange=row.exchange).vt_symbol)
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
        return f"本地日 K 覆盖不足，请先运行「全市场日 K」或「补全本地日 K」（粗筛 {stats.prefilter_total} 只，可算信号 0 只）。"
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
    filtered = apply_screening_filters(list(snapshot.rows))
    min_bars = horizon_min_signal_bars(config)
    k_ready = collect_daily_k_ready_vt_symbols(min_bars, config=config)
    candidates: list[dict[str, Any]] = []
    for row in filtered:
        vt_symbol = str(row.get("vt_symbol") or "").strip()
        if not vt_symbol or vt_symbol in exclusion:
            continue
        if vt_symbol not in k_ready:
            continue
        candidates.append(coerce_quote_row(row).to_dict())

    excluded_count = len(exclusion)
    if not candidates:
        return [], HorizonScanStats(
            scanned_total=scanned_total,
            excluded_count=excluded_count,
            prefilter_total=0,
            refined_total=0,
            kline_missing=0,
        )

    ranked = sorted(candidates, key=_quote_liquidity_key, reverse=True)
    cap = max(1, min(int(max_items), HORIZON_PREFILTER_TOP))
    prefilter = [str(row.get("vt_symbol") or "").strip() for row in ranked[:cap]]
    prefilter = [vt for vt in prefilter if vt]
    return prefilter, HorizonScanStats(
        scanned_total=scanned_total,
        excluded_count=excluded_count,
        prefilter_total=len(prefilter),
        refined_total=0,
        kline_missing=0,
    )


def batch_build_signal_snapshots(
    vt_symbols: list[str],
    *,
    config: WatchlistSignalConfig | None = None,
) -> dict[str, SignalSnapshot]:
    from vnpy_ashare.quotes.radar.radar_signals import build_signal_snapshot

    if not vt_symbols:
        return {}
    cfg = (config or load_outlook_signal_config()).normalized()

    def worker(vt_symbol: str) -> tuple[str, SignalSnapshot] | None:
        snapshot = build_signal_snapshot(vt_symbol, config=cfg)
        if snapshot is None:
            return None
        return vt_symbol, snapshot

    workers = pattern_load_max_workers(item_count=len(vt_symbols))
    pairs = run_parallel_map(vt_symbols, worker, max_workers=workers)
    result: dict[str, SignalSnapshot] = {}
    for item in pairs:
        if item is None:
            continue
        vt_symbol, snapshot = item
        result[vt_symbol] = snapshot
    return result


def scan_horizon_variant(
    variant: str,
    *,
    top_n: int = 8,
    config: WatchlistSignalConfig | None = None,
    exclusion: set[str] | None = None,
    prefilter: list[str] | None = None,
    snapshots: dict[str, SignalSnapshot] | None = None,
    base_stats: HorizonScanStats | None = None,
    scenario_metrics: list | None = None,
) -> HorizonScanResult:
    """扫描单一展望变体（关注/可持/情景）。"""
    cfg = (config or load_outlook_signal_config()).normalized()
    excluded = exclusion if exclusion is not None else collect_outlook_exclusion_vt_symbols()

    if prefilter is None or base_stats is None:
        prefilter_list, stats = prefilter_horizon_universe(excluded, config=cfg)
        prefilter = prefilter_list
        base_stats = stats
        snapshots = batch_build_signal_snapshots(prefilter, config=cfg)
    elif snapshots is None:
        snapshots = batch_build_signal_snapshots(prefilter, config=cfg)

    assert prefilter is not None
    assert base_stats is not None
    assert snapshots is not None

    kline_missing = 0
    refined: list[SignalSnapshot] = []
    for vt_symbol in prefilter:
        snapshot = snapshots.get(vt_symbol)
        if snapshot is None:
            continue
        if signal_missing_kline(snapshot):
            kline_missing += 1
            continue
        refined.append(snapshot)

    if variant in SCENARIO_VARIANTS:
        metrics_list = scenario_metrics if scenario_metrics is not None else batch_build_scenario_metrics(prefilter, snapshots)
        matched_metrics = filter_scenario_metrics(metrics_list, variant=variant)
        matched_metrics.sort(key=lambda item: scenario_sort_key(item, variant=variant), reverse=True)
        name_map = name_map_for_symbols([item.snapshot.vt_symbol for item in matched_metrics[:top_n]])
        rows = build_scenario_rows(tuple(matched_metrics[:top_n]), variant=variant, name_map=name_map)
    else:
        if variant == "avoid_next":
            matched = filter_avoid_snapshots(refined)
            matched.sort(key=lambda snap: outlook_sort_key(snap, variant=variant))
        else:
            matched = filter_outlook_snapshots(refined, variant=variant)
            if variant == "watch_next":
                matched.sort(key=lambda snap: outlook_sort_key(snap, variant=variant), reverse=True)
            else:
                matched.sort(key=lambda snap: outlook_sort_key(snap, variant=variant))
        top_matched = matched[:top_n]
        name_map = name_map_for_symbols([snap.vt_symbol for snap in top_matched])
        metrics_list = scenario_metrics if scenario_metrics is not None else batch_build_scenario_metrics(prefilter, snapshots)
        scenario_hints: dict[str, str] = {}
        for metrics in metrics_list:
            hint = classify_scenario_hint(metrics)
            if hint:
                scenario_hints[metrics.snapshot.vt_symbol] = hint
        rows = build_outlook_rows(
            tuple(top_matched),
            name_map=name_map,
            scenario_hints=scenario_hints,
        )
    computed_at = format_china_datetime_minute()
    stats = HorizonScanStats(
        scanned_total=base_stats.scanned_total,
        excluded_count=base_stats.excluded_count,
        prefilter_total=base_stats.prefilter_total,
        refined_total=len(refined),
        kline_missing=kline_missing,
    )
    result = HorizonScanResult(
        variant=variant,
        rows=rows,
        stats=stats,
        strategy_key=cfg.cache_key(),
        computed_at=computed_at,
    )
    put_horizon_cache(
        variant,
        result.rows,
        scanned_total=stats.scanned_total,
        excluded_count=stats.excluded_count,
        prefilter_total=stats.prefilter_total,
        refined_total=stats.refined_total,
        kline_missing=stats.kline_missing,
        strategy_key=result.strategy_key,
        computed_at=computed_at,
    )
    return result


HORIZON_SCAN_VARIANTS: tuple[str, ...] = (
    "watch_next",
    "hold_next",
    "scenario_bull",
    "scenario_volatile",
    "scenario_bear",
)


def run_horizon_outlook_scan(
    *,
    top_n: int = 8,
    variants: tuple[str, ...] = HORIZON_SCAN_VARIANTS,
) -> tuple[HorizonScanResult, ...]:
    """一次粗筛 + 批量算信号，产出关注/可持/情景榜。"""
    exclusion = collect_outlook_exclusion_vt_symbols()
    prefilter, base_stats = prefilter_horizon_universe(exclusion)
    cfg = load_outlook_signal_config().normalized()
    snapshots = batch_build_signal_snapshots(prefilter, config=cfg)
    scenario_metrics = batch_build_scenario_metrics(prefilter, snapshots)

    results: list[HorizonScanResult] = []
    for variant in variants:
        result = scan_horizon_variant(
            variant,
            top_n=top_n,
            config=cfg,
            exclusion=exclusion,
            prefilter=prefilter,
            snapshots=snapshots,
            base_stats=base_stats,
            scenario_metrics=scenario_metrics if variant in SCENARIO_VARIANTS else None,
        )
        results.append(result)
    return tuple(results)


def cache_entry_from_scan(result: HorizonScanResult) -> HorizonCacheEntry:
    return HorizonCacheEntry(
        variant=result.variant,
        rows=result.rows,
        scanned_total=result.stats.scanned_total,
        excluded_count=result.stats.excluded_count,
        prefilter_total=result.stats.prefilter_total,
        refined_total=result.stats.refined_total,
        kline_missing=result.stats.kline_missing,
        strategy_key=result.strategy_key,
        computed_at=result.computed_at,
    )
