"""自选页策略信号批量刷新。"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from vnpy.trader.ui import QtCore

from vnpy_ashare.config.preferences.watchlist_signal import (
    WatchlistSignalConfig,
    normalize_signal_panel_symbols,
    save_watchlist_signal_config,
)
from vnpy_ashare.data.bar_health import format_meta_date
from vnpy_ashare.domain.symbols.stock import canonical_vt_symbol, lookup_by_vt_symbol
from vnpy_ashare.domain.time.china import format_china_time_hm
from vnpy_ashare.domain.trading.signal_snapshot import SignalSnapshot, detect_signal_transitions, signal_as_of_stale
from vnpy_ashare.domain.trading.stock_continuation import StockContinuationSnapshot
from vnpy_ashare.storage.cache.watchlist_signal_cache import WatchlistSignalDiskCache
from vnpy_ashare.ui.quotes._host_widget import as_qwidget
from vnpy_ashare.ui.quotes.page.run_log import append_run_log
from vnpy_ashare.ui.quotes.watchlist.host import WatchlistHost
from vnpy_ashare.ui.quotes.watchlist_signals.panel import WatchlistSignalPanel
from vnpy_ashare.ui.quotes.watchlist_signals.worker import unwrap_worker_payload

if TYPE_CHECKING:
    from vnpy_ashare.services.analysis import AnalysisService
    from vnpy_ashare.ui.quotes.watchlist.strategy_batch import WatchlistStrategyBatchCoordinator


class WatchlistSignalController:
    """自选池策略信号：仅监控信号区名单。"""

    _SERVICE_RETRY_MS = 800
    _SERVICE_RETRY_TOAST_AT = 5
    _SERVICE_RETRY_MAX = 12

    def __init__(self, page: WatchlistHost) -> None:
        self._page = page
        self._pending_refresh: tuple[bool, list[str] | None] | None = None
        self._deferred_refresh: tuple[bool, list[str] | None] | None = None
        self._service_retry_timer: QtCore.QTimer | None = None
        self._service_retry_count = 0
        self._disk_cache = WatchlistSignalDiskCache()
        self._last_panel_symbols: set[str] = set()

    def _compute_enabled(self) -> bool:
        """是否允许自动策略 Worker（关闭时仍展示已有 cache）。"""
        if not self._page.config.show_watchlist_signals or self._page.page_name != "自选":
            return False
        panel = getattr(self._page, "signal_panel", None)
        return panel is not None and panel.enabled

    def _should_submit_worker(self, *, force: bool) -> bool:
        """手动刷新 / 新加入名单必须算；自动巡检才受「启用信号」约束。"""
        if force:
            return True
        return self._compute_enabled()

    def _enabled(self) -> bool:
        return self._compute_enabled()

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
        snap = lookup_by_vt_symbol(cache, vt_symbol)
        if snap is None or snap.strategy_id != expected_config.class_name:
            return False
        return not signal_as_of_stale(snap, bar_end_date=self._bar_end_date(vt_symbol))

    def _symbols_needing_refresh(self, symbols: list[str]) -> list[str]:
        return [symbol for symbol in symbols if not self._cache_valid(symbol)]

    def _strategy_batch(self) -> WatchlistStrategyBatchCoordinator | None:
        return getattr(self._page, "_strategy_batch", None)

    def stop(self) -> None:
        self._pending_refresh = None
        self._deferred_refresh = None
        self._service_retry_count = 0
        timer = self._service_retry_timer
        if timer is not None:
            timer.stop()
            self._service_retry_timer = None

    @property
    def is_waiting_for_service(self) -> bool:
        return self._deferred_refresh is not None and self._analysis_service() is None

    def _canonicalize_symbols(self, symbols: list[str]) -> list[str]:
        cleaned: list[str] = []
        for vt in symbols:
            text = canonical_vt_symbol(vt) or str(vt or "").strip()
            if text:
                cleaned.append(text)
        return normalize_signal_panel_symbols(cleaned)

    def _schedule_service_retry(self, *, force: bool, symbols: list[str] | None) -> None:
        if self._analysis_service() is not None:
            self._service_retry_count = 0
            return
        self._deferred_refresh = (force, symbols)
        timer = self._service_retry_timer
        if timer is None:
            timer = QtCore.QTimer(as_qwidget(self._page))
            timer.setSingleShot(True)
            timer.timeout.connect(self._on_service_retry)
            self._service_retry_timer = timer
        if not timer.isActive():
            timer.start(self._SERVICE_RETRY_MS)

    def _on_service_retry(self) -> None:
        pending = self._deferred_refresh
        if pending is None or not self._page._active:
            return
        if self._analysis_service() is None:
            self._service_retry_count += 1
            if self._service_retry_count == self._SERVICE_RETRY_TOAST_AT:
                self._page._toast.warning("策略分析服务尚未就绪，信号计算排队中…")
                append_run_log(self._page, "[策略信号] 等待 AnalysisService 就绪")
            if self._service_retry_count >= self._SERVICE_RETRY_MAX:
                self._deferred_refresh = None
                self._service_retry_count = 0
                self._page._toast.warning("策略分析服务不可用，请稍后重试刷新")
                append_run_log(self._page, "[策略信号] AnalysisService 长时间不可用，已停止重试")
                panel = getattr(self._page, "signal_panel", None)
                if panel is not None:
                    panel.render_panel()
                return
            self._schedule_service_retry(force=pending[0], symbols=pending[1])
            panel = getattr(self._page, "signal_panel", None)
            if panel is not None:
                panel.render_panel()
            return
        self._deferred_refresh = None
        self._service_retry_count = 0
        force, symbols = pending
        self.refresh(force=force, symbols=symbols)

    @property
    def is_refreshing(self) -> bool:
        batch = self._strategy_batch()
        if batch is not None:
            return batch.is_refreshing_zone("signal")
        return False

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

    def _normalize_cache_keys(self, updates: Mapping[str, object]) -> dict[str, object]:
        normalized: dict[str, object] = {}
        for vt, value in updates.items():
            if value is None:
                continue
            snap_vt = str(getattr(value, "vt_symbol", "") or "")
            key = canonical_vt_symbol(vt) or canonical_vt_symbol(snap_vt) or str(vt or "").strip()
            if key:
                normalized[key] = value
        return normalized

    def _normalize_signal_updates(self, updates: dict[str, SignalSnapshot]) -> dict[str, SignalSnapshot]:
        raw = self._normalize_cache_keys(dict(updates))
        return {key: value for key, value in raw.items() if isinstance(value, SignalSnapshot)}

    def _normalize_continuation_updates(
        self,
        updates: Mapping[str, object],
    ) -> dict[str, StockContinuationSnapshot]:
        raw = self._normalize_cache_keys(dict(updates))
        return {key: value for key, value in raw.items() if isinstance(value, StockContinuationSnapshot)}

    def _parse_worker_payload(self, raw: dict | object) -> tuple[dict[str, SignalSnapshot], dict[str, object]]:
        payload = unwrap_worker_payload(raw)
        signals = {
            str(vt): snap
            for vt, snap in payload.signals.items()
            if isinstance(snap, SignalSnapshot)
        }
        continuations = dict(payload.continuations or {})
        return signals, continuations

    def _commit_signal_cache(
        self,
        panel_symbols: list[str],
        cache: dict[str, SignalSnapshot],
    ) -> dict[str, SignalSnapshot]:
        """将 Worker 结果按面板名单写入 signal_cache（兼容多种 vt_symbol 键）。"""
        if not cache:
            return {}

        by_key: dict[str, SignalSnapshot] = {}
        for vt, snap in cache.items():
            if not isinstance(snap, SignalSnapshot):
                continue
            for key in (
                str(vt),
                canonical_vt_symbol(str(vt)) or "",
                snap.vt_symbol,
                canonical_vt_symbol(snap.vt_symbol) or "",
            ):
                if key:
                    by_key[key] = snap

        committed: dict[str, SignalSnapshot] = {}
        for panel_vt in panel_symbols:
            canon = canonical_vt_symbol(panel_vt) or panel_vt
            matched: SignalSnapshot | None = (
                by_key.get(panel_vt)
                or by_key.get(canon)
                or lookup_by_vt_symbol(cache, panel_vt)
            )
            if matched is not None:
                committed[canon] = matched
        return committed

    def _needs_continuation_enrich(self) -> bool:
        panel = getattr(self._page, "signal_panel", None)
        if panel is None or not panel.is_expanded():
            return False
        table = getattr(panel, "_table_view", None)
        if table is None:
            return True
        visible = table.visible_column_keys()
        return any(key in {"continuation_pattern", "outlook_compact"} for key in visible)

    def _apply_refresh_result(self, *, worker_completed: bool = False) -> None:
        symbols = self._panel_symbols()
        panel = getattr(self._page, "signal_panel", None)
        if panel is not None:
            has_snapshots = bool(symbols) and any(
                lookup_by_vt_symbol(self._page.signal_cache, vt) is not None for vt in symbols
            )
            if has_snapshots:
                panel.set_updated_at(format_china_time_hm())
            panel.render_panel()
        self._sync_chart_signal_reference()
        if self._page.config.show_watchlist_multiview:
            self._page._multiview.on_signal_or_position_updated()
        if symbols and self._needs_continuation_enrich():
            missing = [
                vt
                for vt in symbols
                if lookup_by_vt_symbol(self._page.continuation_cache, vt) is None
                and lookup_by_vt_symbol(self._page.signal_cache, vt) is not None
            ]
            if missing:
                QtCore.QTimer.singleShot(0, lambda syms=list(missing): self._deferred_enrich_continuation(syms))

    def _deferred_enrich_continuation(self, symbols: list[str]) -> None:
        if not self._page._active:
            return
        self._enrich_continuation(symbols)
        panel = getattr(self._page, "signal_panel", None)
        if panel is not None:
            panel.render_panel()

    def on_page_activated(self) -> None:
        """页面激活后冲刷排队中的策略 Worker。"""
        batch = self._strategy_batch()
        if batch is not None:
            batch.flush_pending()

    def _sync_chart_signal_reference(self, *, tickflow_symbols: set[str] | None = None) -> None:
        item = self._page.current_item
        if item is None or self._page.chart_panel is None:
            return
        if tickflow_symbols is not None and item.tickflow_symbol not in tickflow_symbols:
            return
        snap = lookup_by_vt_symbol(self._page.signal_cache, item.vt_symbol)
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
            return str(quote.name)
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

        for line in lines:
            self._page._toast.info(f"策略信号变更：{line}")
            append_run_log(self._page, f"[策略信号] {line}")

    def refresh_quotes_only(self, tickflow_symbols: set[str] | None = None) -> None:
        """WebSocket/REST 行情推送：仅更新信号区受影响行的展示列。"""
        if not self._page.config.show_watchlist_signals or not self._page._active:
            return
        symbols = tickflow_symbols or set()
        if not symbols:
            return
        panel = getattr(self._page, "signal_panel", None)
        if panel is not None:
            panel.update_rows_for_tickflow_symbols(symbols)
        self._sync_chart_signal_reference(tickflow_symbols=symbols)

    def _enrich_continuation(self, symbols: list[str]) -> None:
        if not self._needs_continuation_enrich():
            return
        service = self._analysis_service()
        if service is None or not symbols:
            return
        built = service.enrich_continuation_batch(
            symbols,
            self._page.signal_cache,
            main_engine=self._page._get_main_engine(),
        )
        if built:
            self._page.continuation_cache.update(self._normalize_continuation_updates(built))

    def _ensure_bar_meta(self, symbols: list[str]) -> None:
        items = []
        for vt in symbols:
            item = self._page.find_stock_item(vt)
            if item is not None:
                items.append(item)
        if items:
            self._page._local.ensure_meta_for_items(items)

    def _rekey_signal_cache(self, symbols: list[str]) -> None:
        cache = self._page.signal_cache
        for vt in list(cache):
            canon = canonical_vt_symbol(vt) or vt
            if canon == vt:
                continue
            snap = cache.pop(vt, None)
            if snap is not None and canon not in cache:
                cache[canon] = snap
        cont = self._page.continuation_cache
        for vt in list(cont):
            canon = canonical_vt_symbol(vt) or vt
            if canon == vt:
                continue
            cont_snap = cont.pop(vt, None)
            if cont_snap is not None and canon not in cont:
                cont[canon] = cont_snap

    def _has_local_daily_bars(self, vt_symbol: str) -> bool:
        item = self._page.find_stock_item(vt_symbol)
        if item is None:
            return True
        key = (item.symbol, item.exchange)
        if key not in self._page.downloaded_keys:
            return False
        meta = self._page.bar_meta.get(key)
        if meta is None or meta.end is None:
            return False
        slow = self._page.signal_config.normalized().slow_window
        return meta.count >= slow + 5

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
        self._page.signal_cache.update(self._normalize_signal_updates(hits))
        self._page._signal_cache_config = config
        self._apply_refresh_result()
        return True

    def _panel_symbol_set(self) -> set[str]:
        symbols = self._panel_symbols()
        expanded: set[str] = set(symbols)
        for vt in symbols:
            canon = canonical_vt_symbol(vt)
            if canon:
                expanded.add(canon)
        return expanded

    def _resolve_refresh_targets(
        self,
        panel_symbols: list[str],
        symbols: list[str] | None,
    ) -> list[str]:
        if symbols is None:
            return panel_symbols
        allowed = self._panel_symbol_set()
        target: list[str] = []
        for vt in symbols:
            text = str(vt or "").strip()
            if not text:
                continue
            canon = canonical_vt_symbol(text) or text
            if text in allowed or canon in allowed:
                for candidate in panel_symbols:
                    if candidate == text or candidate == canon:
                        target.append(candidate)
                        break
                else:
                    target.append(text)
        return target

    def _watchlist_pool_vt_symbols(self) -> set[str]:
        return {item.vt_symbol for item in self._page.watchlist_pool_items()}

    def _symbols_missing_cache(self, symbols: list[str]) -> bool:
        return any(lookup_by_vt_symbol(self._page.signal_cache, vt) is None for vt in symbols)

    def on_stock_list_loaded(self) -> None:
        """自选列表加载完成后：校验名单、预热磁盘缓存、增量刷新。"""
        if not self._page.config.show_watchlist_signals:
            return
        symbols = self._panel_symbols()
        self._ensure_bar_meta(symbols)
        self.on_symbols_changed()
        self.hydrate_from_disk()
        missing = self._symbols_missing_cache(symbols)
        self.refresh(force=missing)

    def refresh(self, *, force: bool = False, symbols: list[str] | None = None) -> None:
        if not self._page.config.show_watchlist_signals or not self._page._active:
            return

        panel_symbols = self._panel_symbols()
        panel = getattr(self._page, "signal_panel", None)
        if not panel_symbols:
            self._page.signal_cache.clear()
            self._page.continuation_cache.clear()
            self._page._signal_cache_config = None
            if panel is not None:
                panel.render_panel()
            return

        if (
            panel is not None
            and not panel.is_expanded()
            and not force
            and self._cache_covers(panel_symbols)
        ):
            self._apply_refresh_result()
            return

        service = self._analysis_service()
        if service is None:
            self._schedule_service_retry(force=force, symbols=symbols)
            if panel is not None:
                self._apply_refresh_result()
            return

        if symbols is None:
            target = panel_symbols
        else:
            target = self._resolve_refresh_targets(panel_symbols, symbols)

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
            self._page.signal_cache.update(self._normalize_signal_updates(disk_hits))
        still_need = [vt for vt in to_fetch if lookup_by_vt_symbol(self._page.signal_cache, vt) is None]
        if not still_need:
            self._page._signal_cache_config = config
            self._apply_refresh_result()
            return

        self._ensure_bar_meta(still_need)
        missing_kline = [vt for vt in still_need if not self._has_local_daily_bars(vt)]
        if missing_kline and force:
            names = "、".join(self._resolve_symbol_name(vt) or vt for vt in missing_kline[:3])
            suffix = "…" if len(missing_kline) > 3 else ""
            self._page._toast.warning(f"以下标的本地日 K 不足，请先在数据管理页下载：{names}{suffix}")

        if not self._should_submit_worker(force=force):
            self._page._signal_cache_config = config
            self._apply_refresh_result()
            return

        self._submit_batch(still_need, config=config, config_key=config_key)

    def _submit_batch(self, symbols: list[str], *, config: WatchlistSignalConfig, config_key: str) -> None:
        batch = self._strategy_batch()
        if batch is None:
            self._apply_refresh_result()
            return

        def on_complete(raw: dict | object) -> None:
            pending = self._pending_refresh
            self._pending_refresh = None
            cache, continuations = self._parse_worker_payload(raw)
            panel_symbols = self._panel_symbols()
            committed = self._commit_signal_cache(panel_symbols or symbols, cache)
            before = {vt: lookup_by_vt_symbol(self._page.signal_cache, vt) for vt in committed}
            if committed:
                self._page.signal_cache.update(committed)
            if continuations:
                self._page.continuation_cache.update(self._normalize_continuation_updates(continuations))
            self._page._signal_cache_config = config
            if committed:
                self._disk_cache.put_many(
                    committed,
                    config_key=config_key,
                    bar_as_of_for=self._bar_end_date,
                )
                append_run_log(self._page, f"[策略信号] 计算完成 {len(committed)} 只")
            elif symbols:
                self._page._toast.warning("策略信号未计算出结果，请确认本地日 K 已下载")
                append_run_log(self._page, "[策略信号] 批量计算无结果，请检查本地日 K")
            if self._page._active and committed:
                self._notify_signal_transitions(before, committed)
            self._apply_refresh_result(worker_completed=True)
            if pending is not None and self._page._active:
                pending_force, pending_symbols = pending
                self.refresh(force=pending_force, symbols=pending_symbols)

        def on_failed(msg: str) -> None:
            pending = self._pending_refresh
            self._pending_refresh = None
            self._page._toast.warning(f"策略信号计算失败：{msg}")
            append_run_log(self._page, f"[策略信号] 计算失败：{msg}")
            panel = getattr(self._page, "signal_panel", None)
            if panel is not None:
                panel.render_panel()
            if pending is not None and self._page._active:
                pending_force, pending_symbols = pending
                self.refresh(force=pending_force, symbols=pending_symbols)

        batch.submit(
            zone="signal",
            symbols=symbols,
            config=config,
            on_complete=on_complete,
            on_failed=on_failed,
        )
        append_run_log(
            self._page,
            f"[策略信号] 已提交计算 {len(symbols)} 只：{', '.join(symbols[:5])}{'…' if len(symbols) > 5 else ''}",
        )
        self._apply_refresh_result()

    def _cache_covers(self, symbols: list[str]) -> bool:
        return not self._symbols_needing_refresh(symbols)

    def invalidate_cache(self, *, clear_disk: bool = True) -> None:
        self._page.signal_cache.clear()
        self._page.continuation_cache.clear()
        self._page._signal_cache_config = None
        if clear_disk:
            self._disk_cache.clear()

    def invalidate_memory_cache(self) -> None:
        """手动刷新：仅清内存，保留磁盘快照加速重算。"""
        self.invalidate_cache(clear_disk=False)

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
            self._page.continuation_cache.pop(vt, None)
        self.refresh(symbols=affected)

    def on_symbols_changed(self) -> None:
        panel = getattr(self._page, "signal_panel", None)
        if panel is None:
            return

        known = self._watchlist_pool_vt_symbols()
        if known:
            kept = self._canonicalize_symbols(
                [
                    vt
                    for vt in panel.symbols
                    if vt in known or (canonical_vt_symbol(vt) or "") in known
                ]
            )
        else:
            kept = self._canonicalize_symbols(panel.symbols)

        if kept != panel.symbols:
            panel.set_symbols(kept)
        self._rekey_signal_cache(kept)
        kept_canon = {canonical_vt_symbol(vt) or vt for vt in kept}
        stale = [
            vt
            for vt in list(self._page.signal_cache)
            if vt not in kept and (canonical_vt_symbol(vt) or vt) not in kept_canon
        ]
        for vt in stale:
            self._page.signal_cache.pop(vt, None)
            self._page.continuation_cache.pop(vt, None)
        panel.render_panel()

        previous = self._last_panel_symbols
        current = set(kept)
        added = current - previous
        self._last_panel_symbols = current

        if not kept:
            return

        if added:
            self._ensure_bar_meta(list(added))
            self.refresh(symbols=list(added), force=True)
            return

        missing = self._symbols_needing_refresh(kept)
        if missing:
            self._ensure_bar_meta(missing)
            self.refresh(symbols=missing, force=False)
        elif not known:
            self.refresh(force=True)

    def on_panel_enabled_changed(self, enabled: bool) -> None:
        if enabled:
            symbols = self._panel_symbols()
            self.refresh(force=bool(symbols) and not self._cache_covers(symbols))
        else:
            self._apply_refresh_result()
