"""雷达页未来展望全市场扫描（信号精算与多变体编排）。"""

from __future__ import annotations

from collections.abc import Callable

from vnpy_ashare.config.preferences.watchlist_signal import WatchlistSignalConfig
from vnpy_ashare.data.download_concurrency import run_parallel_map
from vnpy_ashare.data.pattern_bars import pattern_load_max_workers
from vnpy_ashare.domain.radar.horizon import HorizonScanResult, HorizonScanStats
from vnpy_ashare.domain.time.china import format_china_datetime_minute
from vnpy_ashare.domain.trading.signal_snapshot import SignalSnapshot, signal_missing_kline
from vnpy_ashare.quotes.radar.outlook_strategy_prefs import load_outlook_signal_config
from vnpy_ashare.quotes.radar.radar_horizon_cache import HorizonCacheEntry, put_horizon_cache
from vnpy_ashare.quotes.radar.radar_horizon_prefilter import prefilter_horizon_universe
from vnpy_ashare.quotes.radar.radar_horizon_rules import (
    build_outlook_rows,
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
from vnpy_ashare.quotes.radar.radar_pool import collect_outlook_exclusion_vt_symbols, name_map_for_symbols

__all__ = [
    "HORIZON_SCAN_VARIANTS",
    "batch_build_signal_snapshots",
    "cache_entry_from_scan",
    "run_horizon_outlook_scan",
    "run_horizon_outlook_scan_with_predict",
    "scan_horizon_variant",
]

HORIZON_SCAN_VARIANTS: tuple[str, ...] = (
    "watch_next",
    "hold_next",
    "scenario_bull",
    "scenario_volatile",
    "scenario_bear",
)


def batch_build_signal_snapshots(
    vt_symbols: list[str],
    *,
    config: WatchlistSignalConfig | None = None,
    on_complete: Callable[[int, str, tuple[str, SignalSnapshot] | None], None] | None = None,
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
    pairs = run_parallel_map(vt_symbols, worker, max_workers=workers, on_complete=on_complete)
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
        metrics_list = (
            scenario_metrics if scenario_metrics is not None else batch_build_scenario_metrics(prefilter, snapshots)
        )
        matched_metrics = filter_scenario_metrics(metrics_list, variant=variant)
        matched_metrics.sort(key=lambda item: scenario_sort_key(item, variant=variant), reverse=True)
        name_map = name_map_for_symbols([item.snapshot.vt_symbol for item in matched_metrics[:top_n]])
        rows = build_scenario_rows(tuple(matched_metrics[:top_n]), variant=variant, name_map=name_map)
    else:
        matched = filter_outlook_snapshots(refined, variant=variant)
        if variant == "watch_next":
            matched.sort(key=lambda snap: outlook_sort_key(snap, variant=variant), reverse=True)
        else:
            matched.sort(key=lambda snap: outlook_sort_key(snap, variant=variant))
        top_matched = matched[:top_n]
        name_map = name_map_for_symbols([snap.vt_symbol for snap in top_matched])
        # 仅对已匹配标的计算情景标签，避免全量 prefilter 的冗余 scenario_metrics 计算
        top_vt_set = {snap.vt_symbol for snap in top_matched}
        if scenario_metrics is not None:
            metrics_list = [m for m in scenario_metrics if m.snapshot.vt_symbol in top_vt_set]
        else:
            metrics_list = batch_build_scenario_metrics(list(top_vt_set), snapshots)
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


def _run_horizon_outlook_core(
    *,
    top_n: int,
    variants: tuple[str, ...],
) -> tuple[tuple[HorizonScanResult, ...], list[str], HorizonScanStats]:
    """粗筛 + 批量信号；返回 (榜单结果, prefilter, base_stats) 供预测复用。"""
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
            scenario_metrics=scenario_metrics,
        )
        results.append(result)
    return tuple(results), prefilter, base_stats


def run_horizon_outlook_scan(
    *,
    top_n: int = 8,
    variants: tuple[str, ...] = HORIZON_SCAN_VARIANTS,
) -> tuple[HorizonScanResult, ...]:
    """一次粗筛 + 批量算信号，产出关注/可持/情景榜。"""
    results, _, _ = _run_horizon_outlook_core(top_n=top_n, variants=variants)
    return results


def run_horizon_outlook_scan_with_predict(
    *,
    top_n: int = 8,
    variants: tuple[str, ...] = HORIZON_SCAN_VARIANTS,
) -> "tuple[PredictScanResult, tuple[HorizonScanResult, ...]]":
    """一次粗筛 + 批量算信号，产出关注/可持/情景/预测，统一复用粗筛池与行情数据。"""
    from vnpy_ashare.quotes.radar.predict.predict_scan import quote_rows_for_prefilter, scan_predict

    results, prefilter, base_stats = _run_horizon_outlook_core(top_n=top_n, variants=variants)
    quote_rows = quote_rows_for_prefilter(prefilter)
    predict = scan_predict(
        top_n=top_n,
        prefilter=prefilter,
        base_stats=base_stats,
        quote_rows=quote_rows,
        persist=True,
    )
    return predict, results


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
