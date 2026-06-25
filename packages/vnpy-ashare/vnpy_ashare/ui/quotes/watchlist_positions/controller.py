"""自选页持仓策略刷新编排。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vnpy.trader.ui import QtCore

from vnpy_ashare.app.engine_access import get_ashare_engine
from vnpy_ashare.config.preferences.watchlist_signal import WatchlistSignalConfig
from vnpy_ashare.domain.time.china import format_china_time_hm
from vnpy_ashare.domain.trading.position import PositionRecord, build_position_snapshot
from vnpy_ashare.domain.trading.signal_snapshot import signal_as_of_stale
from vnpy_ashare.notifications.core.position_alert_scan import PositionAlertRow, PositionAlertScanInput
from vnpy_ashare.notifications.triggers.position_alerts import scan_position_alerts
from vnpy_ashare.services.bar import format_meta_date
from vnpy_ashare.services.position import get_position_disk_cache_standalone
from vnpy_ashare.trading.exit.overlay import apply_overnight_exit_overlay
from vnpy_ashare.ui.quotes.watchlist.host import WatchlistHost

if TYPE_CHECKING:
    from vnpy_ashare.services.analysis import AnalysisService
    from vnpy_ashare.services.position import PositionService
    from vnpy_ashare.ui.quotes.watchlist.strategy_batch import WatchlistStrategyBatchCoordinator


class WatchlistPositionController:
    """自选页持仓策略：记账 + 退出信号。"""

    def __init__(self, page: WatchlistHost) -> None:
        self._page = page
        self._pending_refresh: tuple[bool, list[str] | None] | None = None
        self._disk_cache_override = None
        self._last_position_symbols: set[str] = set()

    @property
    def _disk_cache(self):
        if self._disk_cache_override is not None:
            return self._disk_cache_override
        service = self._position_service()
        if service is not None:
            return service.get_position_disk_cache()
        return get_position_disk_cache_standalone()

    @_disk_cache.setter
    def _disk_cache(self, value) -> None:
        self._disk_cache_override = value

    def _compute_enabled(self) -> bool:
        if not self._page.config.show_watchlist_positions:
            return False
        panel = getattr(self._page, "position_panel", None)
        return panel is not None and panel.enabled

    def _enabled(self) -> bool:
        return self._compute_enabled()

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

    def cache_covers_panel(self) -> bool:
        record_map = self._record_map()
        if not record_map:
            return True
        return not self._symbols_needing_refresh(list(record_map), record_map)

    def render_on_resume(self) -> None:
        """Tab 复进且 cache 仍有效：仅重绘持仓区，不提交策略 Worker。"""
        if not self._page._active:
            return
        record_map = self._record_map()
        self.on_rows_changed(record_map=record_map)
        self._apply_refresh_result()

    def _strategy_batch(self) -> WatchlistStrategyBatchCoordinator | None:
        return getattr(self._page, "_strategy_batch", None)

    def stop(self) -> None:
        self._pending_refresh = None

    @property
    def is_refreshing(self) -> bool:
        batch = self._strategy_batch()
        if batch is not None:
            return batch.is_refreshing_zone("position")
        return False

    def _rebuild_cache_entry(self, record: PositionRecord, signal) -> None:
        item = self._page.find_stock_item(record.vt_symbol)
        quote = self._page.quote_map.get(item.tickflow_symbol) if item is not None else None
        last_price = quote.last_price if quote and quote.last_price > 0 else None
        snap = build_position_snapshot(record, signal=signal, last_price=last_price)

        snap = apply_overnight_exit_overlay(record, snap, quote=quote)
        self._page.position_cache[record.vt_symbol] = snap

    def _apply_refresh_result(self) -> None:
        panel = getattr(self._page, "position_panel", None)
        if panel is not None:
            panel.set_updated_at(format_china_time_hm())
            panel.render_panel()
        signal_panel = getattr(self._page, "signal_panel", None)
        if signal_panel is not None:
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
        if self._page.config.show_watchlist_multiview:
            self._page._multiview.on_signal_or_position_updated()

    def refresh_quotes_only(self, tickflow_symbols: set[str] | None = None) -> None:
        if not self._page.config.show_watchlist_positions or not self._page._active:
            return
        record_map = self._record_map()
        if tickflow_symbols:
            targets: list[tuple[str, PositionRecord]] = []
            for vt_symbol, record in record_map.items():
                item = self._page.find_stock_item(vt_symbol)
                if item is not None and item.tickflow_symbol in tickflow_symbols:
                    targets.append((vt_symbol, record))
        else:
            targets = list(record_map.items())

        if not targets:
            return

        for _vt_symbol, record in targets:
            cached = self._page.position_cache.get(record.vt_symbol)
            if cached is None:
                continue
            signal = cached.signal_snapshot
            self._rebuild_cache_entry(record, signal)
        panel = getattr(self._page, "position_panel", None)
        if panel is not None:
            if tickflow_symbols:
                panel.update_rows_for_tickflow_symbols(tickflow_symbols)
            else:
                panel.render_panel()
        self._scan_position_alerts()

    def _scan_position_alerts(self) -> None:
        engine = get_ashare_engine(self._page._get_main_engine())
        if engine is None:
            return
        service = engine.notification_service
        if service is None:
            return

        scan_position_alerts(self._build_position_alert_scan_input(), service)

    def _build_position_alert_scan_input(self) -> PositionAlertScanInput:
        page = self._page
        if not page.config.show_watchlist_positions or not page.position_cache:
            return PositionAlertScanInput(enabled=False)

        rows: list[PositionAlertRow] = []
        for vt_symbol, snap in page.position_cache.items():
            item = page.find_stock_item(vt_symbol)
            quote = page.quote_map.get(item.tickflow_symbol) if item is not None else None
            name = item.name if item is not None else vt_symbol
            symbol = item.symbol if item is not None else vt_symbol.split(".", 1)[0]
            rows.append(
                PositionAlertRow(
                    vt_symbol=vt_symbol,
                    name=name,
                    symbol=symbol,
                    snap=snap,
                    quote=quote,
                )
            )
        return PositionAlertScanInput(enabled=True, rows=tuple(rows))

    def hydrate_from_disk(self, *, record_map: dict[str, PositionRecord] | None = None) -> bool:
        """从磁盘恢复策略信号到内存并渲染（冷启动快速展示）。"""
        if record_map is None:
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
        QtCore.QTimer.singleShot(0, self._complete_stock_list_loaded)

    def _complete_stock_list_loaded(self) -> None:
        if not self._page._active:
            return
        record_map = self._record_map()
        self.on_rows_changed(record_map=record_map)
        self.hydrate_from_disk(record_map=record_map)
        self.refresh(force=False, record_map=record_map)

    def refresh(self, *, force: bool = False, symbols: list[str] | None = None, record_map: dict[str, PositionRecord] | None = None) -> None:
        if not self._page.config.show_watchlist_positions or not self._page._active:
            return
        panel = getattr(self._page, "position_panel", None)
        if panel is not None and not panel.is_expanded() and not force:
            self._apply_refresh_result()
            return

        service = self._analysis_service()
        if service is None:
            if panel is not None:
                self._apply_refresh_result()
            return

        if record_map is None:
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
                self._apply_refresh_result()
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

        if not self._compute_enabled():
            self._page._position_cache_config = config
            self._apply_refresh_result()
            return

        self._submit_batch(still_need, config=config, config_key=config_key, record_map=record_map)

    def _submit_batch(
        self,
        symbols: list[str],
        *,
        config: WatchlistSignalConfig,
        config_key: str,
        record_map: dict[str, PositionRecord],
    ) -> None:
        batch = self._strategy_batch()
        if batch is None:
            self._apply_refresh_result()
            return

        def on_complete(raw: object) -> None:
            if not isinstance(raw, dict):
                return
            signal_cache = raw
            pending = self._pending_refresh
            self._pending_refresh = None
            if not self._page._active:
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
            if pending is not None:
                pending_force, pending_symbols = pending
                self.refresh(force=pending_force, symbols=pending_symbols)

        def on_failed(_msg: str) -> None:
            pending = self._pending_refresh
            self._pending_refresh = None
            if pending is not None and self._page._active:
                pending_force, pending_symbols = pending
                self.refresh(force=pending_force, symbols=pending_symbols)

        batch.submit(
            zone="position",
            symbols=symbols,
            config=config,
            on_complete=on_complete,
            on_failed=on_failed,
        )

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

    def on_rows_changed(self, *, record_map: dict[str, PositionRecord] | None = None) -> None:
        if record_map is None:
            record_map = self._record_map()
        kept = set(record_map)
        stale = [vt for vt in list(self._page.position_cache) if vt not in kept]
        for vt in stale:
            self._page.position_cache.pop(vt, None)
        panel = getattr(self._page, "position_panel", None)
        if panel is not None:
            panel.render_panel()
        previous = self._last_position_symbols
        current = set(record_map)
        added = current - previous
        self._last_position_symbols = current
        if added and previous:
            self.refresh(symbols=list(added), force=True)
            return
        missing = self._symbols_needing_refresh(list(record_map), record_map)
        if missing:
            self.refresh(symbols=missing)
        groups = getattr(self._page, "_watchlist_groups", None)
        if groups is not None:
            groups.refresh_groups()

    def on_panel_enabled_changed(self, enabled: bool) -> None:
        if enabled:
            record_map = self._record_map()
            symbols = list(record_map)
            needs = self._symbols_needing_refresh(symbols, record_map) if symbols else []
            self.refresh(force=bool(needs))
        else:
            self._apply_refresh_result()
