"""自选页策略信号批量刷新。"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from vnpy.trader.ui import QtCore

from vnpy_ashare.data.bar_health import format_meta_date
from vnpy_ashare.domain.signal_snapshot import SignalSnapshot, detect_signal_transitions, signal_as_of_stale
from vnpy_ashare.ui.quotes.page.config import WATCHLIST_SIGNAL_REFRESH_MS
from vnpy_ashare.ui.quotes.watchlist_signals.cache import WatchlistSignalDiskCache
from vnpy_ashare.ui.quotes.watchlist_signals.settings import (
    WatchlistSignalConfig,
    save_watchlist_signal_config,
)
from vnpy_ashare.ui.quotes.watchlist_signals.panel import WatchlistSignalPanel
from vnpy_ashare.ui.quotes.watchlist_signals.worker import WatchlistSignalWorker
from vnpy_common.ui.qt_helpers import release_thread

if TYPE_CHECKING:
    from vnpy_ashare.services.analysis_service import AnalysisService
    from vnpy_ashare.ui.quotes.page.quotes_page import QuotesPage


class WatchlistSignalController:
    """自选池策略信号：仅监控信号区名单。"""

    def __init__(self, page: QuotesPage) -> None:
        self._page = page
        self._worker: QtCore.QThread | None = None
        self._pending_refresh: tuple[bool, list[str] | None] | None = None
        self._disk_cache = WatchlistSignalDiskCache()
        self._timer = QtCore.QTimer(page)
        self._timer.timeout.connect(lambda: self.refresh(force=False))

    def _enabled(self) -> bool:
        if not self._page.config.show_watchlist_signals or self._page.page_name != "自选":
            return False
        panel = getattr(self._page, "signal_panel", None)
        return panel is not None and panel.enabled

    def _panel_symbols(self) -> list[str]:
        panel = getattr(self._page, "signal_panel", None)
        if not isinstance(panel, WatchlistSignalPanel):
            return []
        return panel.symbols

    def _analysis_service(self) -> AnalysisService | None:
        return self._page._get_analysis_service()

    def _bar_end_date(self, vt_symbol: str) -> str | None:
        item = self._page.find_stock_item(vt_symbol)
        if item is None:
            return None
        meta = self._page.bar_meta.get((item.symbol, item.exchange))
        if meta is None or meta.end is None:
            return None
        return format_meta_date(meta.end)

    def _cache_valid(self, vt_symbol: str) -> bool:
        cache = self._page.signal_cache
        expected_config = self._page.signal_config.normalized()
        if self._page._signal_cache_config != expected_config:
            return False
        snap = cache.get(vt_symbol)
        if snap is None or snap.strategy_id != expected_config.class_name:
            return False
        return not signal_as_of_stale(snap, bar_end_date=self._bar_end_date(vt_symbol))

    def _symbols_needing_refresh(self, symbols: list[str]) -> list[str]:
        return [symbol for symbol in symbols if not self._cache_valid(symbol)]

    def start(self) -> None:
        """启动定时刷新；搜索过滤时不强制全量重算（避免输入卡顿）。"""
        if not self._page.config.show_watchlist_signals:
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
            for signal in (worker.finished, worker.failed):
                try:
                    signal.disconnect()
                except (TypeError, RuntimeError):
                    pass
            self._release_worker(worker)

    def apply_config(self, config: WatchlistSignalConfig, *, save: bool = True) -> None:
        normalized = config.normalized()
        changed = self._page.signal_config != normalized
        if changed:
            if save:
                save_watchlist_signal_config(normalized)
            self._page.signal_config = normalized
            panel = getattr(self._page, "signal_panel", None)
            if panel is not None:
                panel.apply_config(normalized)
            self.invalidate_cache()
            self.refresh(force=True)
        self._page._positions.on_signal_config_changed(normalized, changed=changed)

    def _apply_refresh_result(self) -> None:
        symbols = self._panel_symbols()
        if symbols:
            subset = {
                vt: snap for vt in symbols if (snap := self._page.signal_cache.get(vt)) is not None and snap.relative_index_pct is None and snap.signal != "na"
            }
            if subset:
                enriched = self._enrich_relative_index(subset)
                self._page.signal_cache.update(enriched)
        panel = getattr(self._page, "signal_panel", None)
        if panel is not None:
            panel.set_updated_at(datetime.now().strftime("%H:%M"))
            panel.render()
        self._sync_chart_signal_reference()

    def _sync_chart_signal_reference(self, *, tickflow_symbols: set[str] | None = None) -> None:
        item = self._page.current_item
        if item is None or self._page.chart_panel is None:
            return
        if tickflow_symbols is not None and item.tickflow_symbol not in tickflow_symbols:
            return
        snap = self._page.signal_cache.get(item.vt_symbol)
        if snap is None:
            return
        quote = self._page.quote_map.get(item.tickflow_symbol)
        cfg = self._page.signal_config.normalized()
        self._page.chart_panel.apply_signal_reference(
            snap,
            quote=quote,
            fast_window=cfg.fast_window,
            slow_window=cfg.slow_window,
        )

    def _resolve_symbol_name(self, vt_symbol: str) -> str:
        item = self._page.find_stock_item(vt_symbol)
        if item is None:
            return ""
        quote = self._page.quote_map.get(item.tickflow_symbol)
        if quote and quote.name:
            return quote.name
        return item.name or ""

    def _notify_signal_transitions(
        self,
        before: dict[str, SignalSnapshot | None],
        after: dict[str, SignalSnapshot],
    ) -> None:
        if not self._enabled():
            return
        lines = detect_signal_transitions(
            before,
            after,
            symbols=list(after),
            name_for=self._resolve_symbol_name,
        )
        from vnpy_ashare.ui.quotes.page.run_log import append_run_log

        for line in lines:
            self._page._toast.info(f"策略信号变更：{line}")
            append_run_log(self._page, f"[策略信号] {line}")

    def refresh_quotes_only(self, tickflow_symbols: set[str] | None = None) -> None:
        """WebSocket/REST 行情推送：仅更新信号区受影响行的展示列。"""
        if not self._page.config.show_watchlist_signals or not self._page._active:
            return
        if not self._enabled():
            return
        symbols = tickflow_symbols or set()
        if not symbols:
            return
        panel = getattr(self._page, "signal_panel", None)
        if panel is not None:
            panel.update_rows_for_tickflow_symbols(symbols)
        self._sync_chart_signal_reference(tickflow_symbols=symbols)

    def _enrich_relative_index(self, cache: dict[str, SignalSnapshot]) -> dict[str, SignalSnapshot]:
        service = self._analysis_service()
        if service is None or not cache:
            return cache
        enriched = service.enrich_relative_index_batch(cache)
        cache.clear()
        cache.update(enriched)
        return cache

    def hydrate_from_disk(self) -> bool:
        """从磁盘恢复上次快照到内存并渲染（重启后立即展示，后台再增量刷新）。"""
        symbols = self._panel_symbols()
        if not symbols:
            return False
        config = self._page.signal_config.normalized()
        hits = self._disk_cache.load_many(
            symbols,
            config_key=config.cache_key(),
            bar_as_of_for=self._bar_end_date,
        )
        if not hits:
            return False
        self._enrich_relative_index(hits)
        self._page.signal_cache.update(hits)
        self._page._signal_cache_config = config
        self._apply_refresh_result()
        return True

    def on_stock_list_loaded(self) -> None:
        """自选列表加载完成后：校验名单、预热磁盘缓存、增量刷新。"""
        if not self._page.config.show_watchlist_signals:
            return
        self.on_symbols_changed()
        self.hydrate_from_disk()
        self.refresh(force=False)

    def refresh(self, *, force: bool = False, symbols: list[str] | None = None) -> None:
        if not self._page.config.show_watchlist_signals or not self._page._active:
            return
        if not self._enabled():
            panel = getattr(self._page, "signal_panel", None)
            if panel is not None:
                panel.render()
            return
        if self._worker is not None and self._worker.isRunning():
            self._pending_refresh = (force, symbols)
            return

        service = self._analysis_service()
        panel_symbols = self._panel_symbols()
        if service is None:
            panel = getattr(self._page, "signal_panel", None)
            if panel is not None:
                panel.render()
            return

        if symbols is None:
            target = panel_symbols
        else:
            allowed = set(panel_symbols)
            target = [vt for vt in symbols if vt in allowed]

        if not panel_symbols:
            self._page.signal_cache.clear()
            self._page._signal_cache_config = None
            panel = getattr(self._page, "signal_panel", None)
            if panel is not None:
                panel.render()
            return

        if not target:
            return

        if force:
            to_fetch = target
        else:
            to_fetch = self._symbols_needing_refresh(target)
            if not to_fetch:
                self._apply_refresh_result()
                return

        config = self._page.signal_config.normalized()
        config_key = config.cache_key()
        disk_hits = self._disk_cache.load_many(
            to_fetch,
            config_key=config_key,
            bar_as_of_for=self._bar_end_date,
        )
        if disk_hits:
            self._enrich_relative_index(disk_hits)
            self._page.signal_cache.update(disk_hits)
        still_need = [vt for vt in to_fetch if vt not in disk_hits]
        if not still_need:
            self._page._signal_cache_config = config
            self._apply_refresh_result()
            return

        worker = WatchlistSignalWorker(
            service,
            symbols=still_need,
            class_name=config.class_name,
            fast_window=config.fast_window,
            slow_window=config.slow_window,
            parent=self._page,
        )
        self._worker = worker

        def on_finished(cache: dict) -> None:
            if self._worker is worker:
                self._worker = None
            pending = self._pending_refresh
            self._pending_refresh = None
            before = {vt: self._page.signal_cache.get(vt) for vt in cache}
            self._enrich_relative_index(cache)
            self._page.signal_cache.update(cache)
            self._page._signal_cache_config = config
            if cache:
                self._disk_cache.put_many(
                    cache,
                    config_key=config_key,
                    bar_as_of_for=self._bar_end_date,
                )
            active = self._page._active
            if active:
                self._notify_signal_transitions(before, cache)
                self._apply_refresh_result()
            self._release_worker(worker)
            if pending is not None and active:
                pending_force, pending_symbols = pending
                self.refresh(force=pending_force, symbols=pending_symbols)

        def on_failed(_msg: str) -> None:
            if self._worker is worker:
                self._worker = None
            pending = self._pending_refresh
            self._pending_refresh = None
            self._release_worker(worker)
            if not self._page._active:
                return
            panel = getattr(self._page, "signal_panel", None)
            if panel is not None:
                panel.render()
            if pending is not None:
                pending_force, pending_symbols = pending
                self.refresh(force=pending_force, symbols=pending_symbols)

        worker.finished.connect(on_finished)
        worker.failed.connect(on_failed)
        worker.start()

    def _cache_covers(self, symbols: list[str]) -> bool:
        return not self._symbols_needing_refresh(symbols)

    def invalidate_cache(self) -> None:
        self._page.signal_cache.clear()
        self._page._signal_cache_config = None
        self._disk_cache.clear()

    def refresh_symbols(self, vt_symbols: list[str]) -> None:
        """日 K 更新后，仅刷新信号区中受影响的标的。"""
        if not self._page.config.show_watchlist_signals:
            return
        panel_symbols = set(self._panel_symbols())
        affected = [vt for vt in vt_symbols if vt in panel_symbols]
        if not affected:
            return
        for vt in affected:
            self._page.signal_cache.pop(vt, None)
        self.refresh(symbols=affected)

    def on_symbols_changed(self) -> None:
        if not self._page.all_stocks:
            return
        known = {item.vt_symbol for item in self._page.all_stocks}
        panel = getattr(self._page, "signal_panel", None)
        if panel is None:
            return
        kept = [vt for vt in panel.symbols if vt in known]
        if kept != panel.symbols:
            panel.set_symbols(kept)
        stale = [vt for vt in list(self._page.signal_cache) if vt not in kept]
        for vt in stale:
            self._page.signal_cache.pop(vt, None)
        panel.render()
        missing = self._symbols_needing_refresh(kept)
        if missing:
            self.refresh(symbols=missing)

    def on_panel_enabled_changed(self, enabled: bool) -> None:
        if enabled:
            self.refresh(force=True)
        else:
            panel = getattr(self._page, "signal_panel", None)
            if panel is not None:
                panel.render()
