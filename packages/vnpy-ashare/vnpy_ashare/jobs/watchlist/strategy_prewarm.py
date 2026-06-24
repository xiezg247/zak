"""自选页策略信号磁盘预热（信号区 + 持仓区）。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vnpy_ashare.ai.context.symbol import parse_stock_symbol
from vnpy_ashare.config.preferences.watchlist_position import load_watchlist_position_config
from vnpy_ashare.config.preferences.watchlist_signal import (
    WatchlistSignalConfig,
    load_signal_panel_symbols,
    load_watchlist_signal_config,
)
from vnpy_ashare.data.bar_health import bar_meta_from_overview, format_meta_date
from vnpy_ashare.domain.trading.position import PositionRecord
from vnpy_ashare.domain.trading.signal_snapshot import signal_as_of_stale
from vnpy_ashare.jobs.core.result import JobResult
from vnpy_ashare.storage.cache.watchlist_position_cache import WatchlistPositionDiskCache
from vnpy_ashare.storage.cache.watchlist_signal_cache import WatchlistSignalDiskCache

if TYPE_CHECKING:
    from vnpy_ashare.app.engine import AshareEngine


def _bar_end_date_for(engine: AshareEngine, vt_symbol: str) -> str | None:
    item = parse_stock_symbol(vt_symbol)
    if item is None:
        return None
    overview = engine.bar_service.get_overview(item.symbol, item.exchange, "daily")
    if overview is None:
        return None
    return format_meta_date(bar_meta_from_overview(overview).end)


def _signal_needs_prewarm(
    vt_symbol: str,
    *,
    config: WatchlistSignalConfig,
    disk: WatchlistSignalDiskCache,
    bar_end_date: str | None,
) -> bool:
    if not bar_end_date:
        return True
    config_key = config.cache_key()
    snap = disk.get(vt_symbol, config_key, bar_end_date) or disk.get_latest(vt_symbol, config_key)
    if snap is None:
        return True
    if snap.strategy_id != config.class_name:
        return True
    return signal_as_of_stale(snap, bar_end_date=bar_end_date)


def _position_needs_prewarm(
    record: PositionRecord,
    *,
    config: WatchlistSignalConfig,
    disk: WatchlistPositionDiskCache,
    bar_end_date: str | None,
) -> bool:
    if not bar_end_date:
        return True
    config_key = config.cache_key()
    pos_key = record.position_key
    snap = disk.get(record.vt_symbol, config_key, bar_end_date, pos_key) or disk.get_latest(
        record.vt_symbol,
        config_key,
        pos_key,
    )
    if snap is None:
        return True
    if snap.strategy_id != config.class_name:
        return True
    return signal_as_of_stale(snap, bar_end_date=bar_end_date)


def prewarm_watchlist_strategy_disks(engine: AshareEngine, *, force: bool = False) -> JobResult:
    """批量重算关注池策略信号并写入磁盘 cache（UI 冷启动 hydrate 用）。"""
    signal_symbols = load_signal_panel_symbols()
    signal_config = load_watchlist_signal_config().normalized()
    position_config = load_watchlist_position_config().normalized()
    position_signal_config = position_config.effective_signal_config(signal_config)

    def bar_end_date_fn(vt: str) -> str | None:
        return _bar_end_date_for(engine, vt)

    signal_disk = WatchlistSignalDiskCache()
    position_disk = WatchlistPositionDiskCache()
    analysis = engine.analysis_service

    signal_targets = list(signal_symbols)
    if not force:
        signal_targets = [
            vt
            for vt in signal_symbols
            if _signal_needs_prewarm(
                vt,
                config=signal_config,
                disk=signal_disk,
                bar_end_date=bar_end_date_fn(vt),
            )
        ]

    position_records = engine.position_service.get_items()
    position_targets = list(position_records)
    if not force:
        position_targets = [
            record
            for record in position_records
            if _position_needs_prewarm(
                record,
                config=position_signal_config,
                disk=position_disk,
                bar_end_date=bar_end_date_fn(record.vt_symbol),
            )
        ]

    if not signal_targets and not position_targets:
        return JobResult(success=True, skipped=True, message="策略磁盘缓存均已就绪")

    signal_written = 0
    if signal_targets:
        cache = analysis.batch_strategy_signals(
            signal_targets,
            class_name=signal_config.class_name,
            fast_window=signal_config.fast_window,
            slow_window=signal_config.slow_window,
        )
        if cache:
            enriched = analysis.enrich_relative_index_batch(cache)
            signal_disk.put_many(
                enriched,
                config_key=signal_config.cache_key(),
                bar_as_of_for=bar_end_date_fn,
            )
            signal_written = len(enriched)

    position_written = 0
    if position_targets:
        symbols = [record.vt_symbol for record in position_targets]
        record_map = {record.vt_symbol: record for record in position_targets}
        cache = analysis.batch_strategy_signals(
            symbols,
            class_name=position_signal_config.class_name,
            fast_window=position_signal_config.fast_window,
            slow_window=position_signal_config.slow_window,
        )
        if cache:
            enriched = analysis.enrich_relative_index_batch(cache)
            position_disk.put_many(
                enriched,
                config_key=position_signal_config.cache_key(),
                position_key_for=lambda vt: record_map[vt].position_key if vt in record_map else None,
                bar_as_of_for=bar_end_date_fn,
            )
            position_written = len(enriched)

    parts: list[str] = []
    if signal_written:
        parts.append(f"信号区 {signal_written} 只")
    if position_written:
        parts.append(f"持仓区 {position_written} 只")
    message = "策略磁盘预热完成：" + " · ".join(parts) if parts else "无可写入快照"
    return JobResult(success=True, message=message)


def warm_watchlist_strategy_cache_job(
    *,
    engine: AshareEngine | None = None,
    force: bool = False,
) -> JobResult:
    if engine is None:
        return JobResult(success=True, skipped=True, message="A 股引擎未就绪")
    try:
        return prewarm_watchlist_strategy_disks(engine, force=force)
    except Exception as ex:
        return JobResult(success=False, message=f"策略磁盘预热失败：{ex}")
