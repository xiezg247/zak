"""自选页持仓策略刷新编排。"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from vnpy.trader.ui import QtCore

from vnpy_ashare.data.bar_health import format_meta_date
from vnpy_ashare.domain.position_snapshot import PositionRecord, build_position_snapshot
from vnpy_ashare.domain.signal_snapshot import signal_as_of_stale
from vnpy_ashare.ui.quotes.page.config import WATCHLIST_SIGNAL_REFRESH_MS
from vnpy_ashare.ui.quotes.watchlist_positions.cache import WatchlistPositionDiskCache
from vnpy_ashare.ui.quotes.watchlist_positions.worker import WatchlistPositionWorker
from vnpy_ashare.ui.quotes.watchlist_signals.settings import WatchlistSignalConfig
from vnpy_common.ui.qt_helpers import release_thread

if TYPE_CHECKING:
    from vnpy_ashare.services.analysis_service import AnalysisService
    from vnpy_ashare.services.position_service import PositionService
    from vnpy_ashare.ui.quotes.page.quotes_page import QuotesPage


class WatchlistPositionController:
    """自选页持仓策略：记账 + 退出信号。"""

    def __init__(self, page: QuotesPage) -> None:
        self._page = page
        self._worker: QtCore.QThread | None = None
        self._pending_refresh: tuple[bool, list[str] | None] | None = None
        self._disk_cache = WatchlistPositionDiskCache()
        self._timer = QtCore.QTimer(page)
        self._timer.timeout.connect(lambda: self.refresh(force=False))

    def _enabled(self) -> bool:
        if not self._page.config.show_watchlist_positions or self._page.page_name != "自选":
            return False
        panel = getattr(self._page, "position_panel", None)
        return panel is not None and panel.enabled

    def _position_service(self) -> PositionService | None:
        return self._page._get_position_service()

    def _analysis_service(self) -> AnalysisService | None:
        return self._page._get_analysis_service()

    def _records(self) -> list[PositionRecord]:
        service = self._position_service()
        if service is None:
            return []
        return service.get_items()

    def _record_map(self) -> dict[str, PositionRecord]:
        return {record.vt_symbol: record for record in self._records()}

    def _follows_signal(self) -> bool:
        panel = getattr(self._page, "position_panel", None)
        if panel is not None:
            return bool(panel.read_config().follow_signal)
        return self._page.position_config.follow_signal

    def _cache_strategy_mismatch(self, signal_config: WatchlistSignalConfig) -> bool:
        expected = signal_config.class_name
        for snap in self._page.position_cache.values():
            signal = snap.signal_snapshot
            if signal is not None and signal.strategy_id != expected:
                return True
        return False

    def on_signal_config_changed(
        self,
        signal_config: WatchlistSignalConfig,
        *,
        changed: bool = True,
    ) -> None:
        """信号区策略变更时，跟随模式下同步刷新持仓退出信号。"""
        if not self._page.config.show_watchlist_positions:
            return
        panel = getattr(self._page, "position_panel", None)
        if panel is not None:
            panel.sync_follow_display(signal_config)
        if not self._follows_signal():
            return
        if changed or self._cache_strategy_mismatch(signal_config):
            self.invalidate_cache()
            self.refresh(force=True)
        elif panel is not None:
            panel.render_panel()

    def _effective_config(self) -> WatchlistSignalConfig:
        page = self._page
        return page.position_config.normalized().effective_signal_config(page.signal_config)

    def _bar_end_date(self, vt_symbol: str) -> str | None:
        item = self._page.find_stock_item(vt_symbol)
        if item is None:
            return None
        meta = self._page.bar_meta.get((item.symbol, item.exchange))
        if meta is None or meta.end is None:
            return None
        return format_meta_date(meta.end)

    def _cache_valid(self, vt_symbol: str, record: PositionRecord) -> bool:
        expected_config = self._effective_config()
        if self._page._position_cache_config != expected_config:
            return False
        snap = self._page.position_cache.get(vt_symbol)
        if snap is None:
            return False
        if snap.cost_price != record.cost_price or snap.volume != record.volume or snap.buy_date != record.buy_date:
            return False
        signal = snap.signal_snapshot
        if signal is None or signal.strategy_id != expected_config.class_name:
            return False
        return not signal_as_of_stale(signal, bar_end_date=self._bar_end_date(vt_symbol))

    def _symbols_needing_refresh(self, symbols: list[str], record_map: dict[str, PositionRecord]) -> list[str]:
        return [symbol for symbol in symbols if not self._cache_valid(symbol, record_map[symbol])]

    def start(self) -> None:
        if not self._page.config.show_watchlist_positions:
            return
        self._timer.setInterval(WATCHLIST_SIGNAL_REFRESH_MS)
        if not self._timer.isActive():
            self._timer.start()

    def _release_worker(self, worker: QtCore.QThread | None) -> None:
        if worker is None:
            return
        release_thread(self._page._retired_workers, worker, timeout_ms=0)

    def stop(self) -> None:
        self._timer.stop()
        self._pending_refresh = None
        worker = self._worker
        if worker is not None:
            self._worker = None
            self._release_worker(worker)

    def _rebuild_cache_entry(self, record: PositionRecord, signal) -> None:
        item = self._page.find_stock_item(record.vt_symbol)
        quote = self._page.quote_map.get(item.tickflow_symbol) if item is not None else None
        last_price = quote.last_price if quote and quote.last_price > 0 else None
        snap = build_position_snapshot(record, signal=signal, last_price=last_price)
        self._page.position_cache[record.vt_symbol] = snap

    def _apply_refresh_result(self) -> None:
        panel = getattr(self._page, "position_panel", None)
        if panel is not None:
            panel.set_updated_at(datetime.now().strftime("%H:%M"))
            panel.render_panel()
        signal_panel = getattr(self._page, "signal_panel", None)
        if signal_panel is not None and signal_panel.enabled:
            signal_panel.render_panel()
        item = self._page.current_item
        if item is not None and self._page.chart_panel is not None:
            snap = self._page.position_cache.get(item.vt_symbol)
            if snap is not None and snap.signal_snapshot is not None:
                quote = self._page.quote_map.get(item.tickflow_symbol)
                pos_cfg = self._page.position_config.normalized().effective_signal_config(self._page.signal_config)
                self._page.chart_panel.apply_signal_reference(
                    snap.signal_snapshot,
                    quote=quote,
                    fast_window=pos_cfg.fast_window,
                    slow_window=pos_cfg.slow_window,
                )

    def refresh_quotes_only(self) -> None:
        if not self._page.config.show_watchlist_positions or not self._page._active:
            return
        record_map = self._record_map()
        for vt_symbol, record in record_map.items():
            cached = self._page.position_cache.get(vt_symbol)
            if cached is None:
                continue
            signal = cached.signal_snapshot
            self._rebuild_cache_entry(record, signal)
        panel = getattr(self._page, "position_panel", None)
        if panel is not None:
            panel.render_panel()

    def hydrate_from_disk(self) -> bool:
        """从磁盘恢复策略信号到内存并渲染（冷启动快速展示）。"""
        record_map = self._record_map()
        symbols = list(record_map)
        if not symbols:
            return False
        config = self._effective_config()
        hits = self._disk_cache.load_many(
            symbols,
            config_key=config.cache_key(),
            position_key_for=lambda vt: record_map[vt].position_key if vt in record_map else None,
            bar_as_of_for=self._bar_end_date,
        )
        if not hits:
            return False
        for vt_symbol, signal in hits.items():
            record = record_map.get(vt_symbol)
            if record is None:
                continue
            self._rebuild_cache_entry(record, signal)
        self._page._position_cache_config = config
        self._apply_refresh_result()
        return True

    def on_stock_list_loaded(self) -> None:
        if not self._page.config.show_watchlist_positions:
            return
        self.on_rows_changed()
        self.hydrate_from_disk()
        self.refresh(force=False)

    def refresh(self, *, force: bool = False, symbols: list[str] | None = None) -> None:
        if not self._page.config.show_watchlist_positions or not self._page._active:
            return
        if not self._enabled():
            panel = getattr(self._page, "position_panel", None)
            if panel is not None:
                panel.render_panel()
            return
        if self._worker is not None and self._worker.isRunning():
            self._pending_refresh = (force, symbols)
            return

        service = self._analysis_service()
        if service is None:
            return

        record_map = self._record_map()
        all_symbols = list(record_map)
        if symbols is None:
            target = all_symbols
        else:
            allowed = set(all_symbols)
            target = [vt for vt in symbols if vt in allowed]

        if not all_symbols:
            self._page.position_cache.clear()
            self._page._position_cache_config = None
            panel = getattr(self._page, "position_panel", None)
            if panel is not None:
                panel.render_panel()
            return

        if not target:
            return

        if force:
            to_fetch = target
        else:
            to_fetch = self._symbols_needing_refresh(target, record_map)
            if not to_fetch:
                return

        config = self._effective_config()
        config_key = config.cache_key()
        disk_hits = self._disk_cache.load_many(
            to_fetch,
            config_key=config_key,
            position_key_for=lambda vt: record_map[vt].position_key if vt in record_map else None,
            bar_as_of_for=self._bar_end_date,
        )
        if disk_hits:
            for vt_symbol, signal in disk_hits.items():
                record = record_map.get(vt_symbol)
                if record is None:
                    continue
                self._rebuild_cache_entry(record, signal)
        still_need = [vt for vt in to_fetch if vt not in disk_hits]
        if not still_need:
            self._page._position_cache_config = config
            self._apply_refresh_result()
            return

        worker = WatchlistPositionWorker(
            service,
            symbols=still_need,
            class_name=config.class_name,
            fast_window=config.fast_window,
            slow_window=config.slow_window,
        )
        self._worker = worker

        def on_finished(signal_cache: dict) -> None:
            if self._worker is worker:
                self._worker = None
            pending = self._pending_refresh
            self._pending_refresh = None
            if not self._page._active:
                self._release_worker(worker)
                return
            records = self._record_map()
            for vt_symbol, signal in signal_cache.items():
                record = records.get(vt_symbol)
                if record is None:
                    continue
                self._rebuild_cache_entry(record, signal)
            self._page._position_cache_config = config
            if signal_cache:
                self._disk_cache.put_many(
                    signal_cache,
                    config_key=config_key,
                    position_key_for=lambda vt: records[vt].position_key if vt in records else None,
                    bar_as_of_for=self._bar_end_date,
                )
            stale = [vt for vt in list(self._page.position_cache) if vt not in records]
            for vt in stale:
                self._page.position_cache.pop(vt, None)
            self._apply_refresh_result()
            self._release_worker(worker)
            if pending is not None:
                pending_force, pending_symbols = pending
                self.refresh(force=pending_force, symbols=pending_symbols)

        def on_failed(_msg: str) -> None:
            if self._worker is worker:
                self._worker = None
            pending = self._pending_refresh
            self._pending_refresh = None
            self._release_worker(worker)
            if pending is not None and self._page._active:
                pending_force, pending_symbols = pending
                self.refresh(force=pending_force, symbols=pending_symbols)

        worker.finished.connect(on_finished)
        worker.failed.connect(on_failed)
        worker.start()

    def invalidate_cache(self) -> None:
        self._page.position_cache.clear()
        self._page._position_cache_config = None
        self._disk_cache.clear()

    def refresh_symbols(self, vt_symbols: list[str]) -> None:
        if not self._page.config.show_watchlist_positions:
            return
        record_map = self._record_map()
        affected = [vt for vt in vt_symbols if vt in record_map]
        if not affected:
            return
        for vt in affected:
            self._page.position_cache.pop(vt, None)
        self.refresh(symbols=affected)

    def on_rows_changed(self) -> None:
        record_map = self._record_map()
        kept = set(record_map)
        stale = [vt for vt in list(self._page.position_cache) if vt not in kept]
        for vt in stale:
            self._page.position_cache.pop(vt, None)
        panel = getattr(self._page, "position_panel", None)
        if panel is not None:
            panel.render_panel()
        missing = self._symbols_needing_refresh(list(record_map), record_map)
        if missing:
            self.refresh(symbols=missing)

    def on_panel_enabled_changed(self, enabled: bool) -> None:
        if enabled:
            self.refresh(force=True)
        else:
            panel = getattr(self._page, "position_panel", None)
            if panel is not None:
                panel.render_panel()
