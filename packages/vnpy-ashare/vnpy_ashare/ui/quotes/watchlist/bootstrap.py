"""自选页加载编排：池同步、下游刷新去重、预设感知调度。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from vnpy.trader.ui import QtCore

from vnpy_ashare.domain.symbols.stock import StockItem
from vnpy_ashare.ui.quotes.features.watchlist.prefs import LayoutPresetId, load_watchlist_layout_preset
from vnpy_ashare.ui.quotes.page.roles import STRATEGY_MONITOR_PAGE, uses_watchlist_pool

if TYPE_CHECKING:
    from vnpy_ashare.ui.quotes.watchlist.host import WatchlistHost

ScheduleReason = Literal["tab_resume", "pool_ready", "pool_mutation", "universe_load"]


class WatchlistBootstrapCoordinator:
    """自选页唯一下游调度入口，避免 activate 与 load_stock_list 重复刷新。"""

    def __init__(self) -> None:
        self._last_pool_fingerprint: str | None = None
        self._downstream_flush_pending = False
        self._downstream_dirty = False
        self._last_schedule_reason: ScheduleReason = "pool_ready"

    @staticmethod
    def pool_fingerprint(stocks: list[StockItem]) -> str:
        return "|".join(f"{item.symbol}:{item.exchange.value}" for item in stocks)

    def on_activate(self, page: WatchlistHost) -> None:
        if not uses_watchlist_pool(page.page_name):
            page.load_stock_list()
            return

        pool = page._watchlist._pool_from_service()
        fingerprint = self.pool_fingerprint(pool)
        if (
            page.display_stocks
            and self._last_pool_fingerprint is not None
            and fingerprint == self._last_pool_fingerprint
        ):
            self._sync_display_only(page, pool)
            self.schedule_downstream(page, reason="tab_resume")
            return

        self.on_pool_ready(page, pool, source="pool_ready")

    def reload_watchlist_pool(
        self,
        page: WatchlistHost,
        *,
        source: ScheduleReason = "pool_ready",
    ) -> None:
        """同步读取自选池（不经 UniverseLoadWorker / K 线 overview 预热）。"""
        if not uses_watchlist_pool(page.page_name):
            page.load_stock_list()
            return
        pool = page._watchlist._pool_from_service()
        self.on_pool_ready(page, pool, source=source)

    @staticmethod
    def _apply_strategy_pool(page: WatchlistHost, pool: list[StockItem]) -> None:
        page.all_stocks = list(pool)
        page.display_stocks = list(pool)
        page._watchlist.refresh_keys()
        monitor = getattr(page, "_strategy_monitor_feature", None)
        if monitor is not None:
            monitor.refresh_context_bar()
        status = getattr(page, "status_label", None)
        if status is not None:
            status.setText(f"自选池 {len(pool)} 只")

    def _sync_pool_display(self, page: WatchlistHost, pool: list[StockItem]) -> None:
        page.watchlist_pool_stocks = list(pool)
        if page.page_name == STRATEGY_MONITOR_PAGE:
            self._apply_strategy_pool(page, pool)
            return
        if page._watchlist_groups is not None:
            page._watchlist_groups.on_stock_list_loaded(pool)
        else:
            page.all_stocks = list(pool)
            page.apply_filter()
        page._watchlist.refresh_keys()
        feature = getattr(page, "_watchlist_feature", None)
        if feature is not None:
            feature.refresh_context_bar()

    def on_pool_ready(
        self,
        page: WatchlistHost,
        stocks: list[StockItem],
        *,
        source: ScheduleReason,
    ) -> None:
        if not uses_watchlist_pool(page.page_name):
            return

        self._last_pool_fingerprint = self.pool_fingerprint(stocks)

        if page.page_name == STRATEGY_MONITOR_PAGE:
            page.watchlist_pool_stocks = list(stocks)
            self._apply_strategy_pool(page, stocks)
            monitor = getattr(page, "_strategy_monitor_feature", None)
            if monitor is not None:
                monitor.on_stock_list_loaded()
        elif page._watchlist_groups is not None:
            page.watchlist_pool_stocks = list(stocks)
            page._watchlist_groups.on_stock_list_loaded(stocks)
        else:
            page.watchlist_pool_stocks = list(stocks)
            page.all_stocks = list(stocks)
            page.apply_filter()
            page._watchlist.refresh_keys()
            feature = getattr(page, "_watchlist_feature", None)
            if feature is not None:
                feature.on_stock_list_loaded()

        page._update_action_buttons()
        self.schedule_downstream(page, reason=source)
        if page.page_name != STRATEGY_MONITOR_PAGE and hasattr(page, "end_tab_switch_loading"):
            page.end_tab_switch_loading()

    def schedule_downstream(self, page: WatchlistHost, *, reason: ScheduleReason) -> None:
        if not uses_watchlist_pool(page.page_name) or not page._active:
            return

        self._last_schedule_reason = reason
        self._downstream_dirty = True
        if self._downstream_flush_pending:
            return
        self._downstream_flush_pending = True
        QtCore.QTimer.singleShot(0, lambda: self._flush_downstream(page))

    def _flush_downstream(self, page: WatchlistHost) -> None:
        self._downstream_flush_pending = False
        if not page._active or not self._downstream_dirty:
            self._downstream_dirty = False
            return
        self._downstream_dirty = False
        self._run_downstream(page, reason=self._last_schedule_reason)
        if self._downstream_dirty and page._active:
            self._downstream_flush_pending = True
            QtCore.QTimer.singleShot(0, lambda: self._flush_downstream(page))

    def invalidate_symbols(self, page: WatchlistHost, vt_symbols: list[str]) -> None:
        for vt_symbol in vt_symbols:
            page.signal_cache.pop(vt_symbol, None)
            page.position_cache.pop(vt_symbol, None)
        if page.config.show_watchlist_multiview and page._multiview.is_multiview_active():
            page._multiview.refresh(force=False, refresh_moneyflow=False)

    def _sync_display_only(self, page: WatchlistHost, pool: list[StockItem]) -> None:
        self._sync_pool_display(page, pool)
        page._update_action_buttons()
        if hasattr(page, "end_tab_switch_loading"):
            page.end_tab_switch_loading()

    def _try_hydrate_downstream_cache(self, page: WatchlistHost) -> None:
        if page.config.show_watchlist_signals:
            page._signals.hydrate_from_disk()
        if page.config.show_watchlist_positions:
            page._positions.hydrate_from_disk()

    def _can_render_only_on_resume(self, page: WatchlistHost) -> bool:
        cfg = page.config
        signals_ok = not cfg.show_watchlist_signals or page._signals.cache_covers_panel()
        positions_ok = not cfg.show_watchlist_positions or page._positions.cache_covers_panel()
        return signals_ok and positions_ok

    def _render_downstream_only(self, page: WatchlistHost) -> None:
        if page.config.show_watchlist_positions:
            page._positions.render_on_resume()
        if page.config.show_watchlist_signals:
            page._signals.render_on_resume()
        if page.config.show_watchlist_multiview and page._multiview.is_multiview_active():
            page._multiview.refresh(force=False, refresh_moneyflow=False)
        if hasattr(page, "end_tab_switch_loading"):
            page.end_tab_switch_loading()

    def _run_downstream(self, page: WatchlistHost, *, reason: ScheduleReason) -> None:
        if page.page_name != STRATEGY_MONITOR_PAGE:
            preset = load_watchlist_layout_preset()
            self._schedule_multiview(page, preset=preset)
            return

        if reason == "tab_resume" and self._can_render_only_on_resume(page):
            self._render_downstream_only(page)
            return

        if reason != "tab_resume":
            self._try_hydrate_downstream_cache(page)
            if self._can_render_only_on_resume(page):
                self._render_downstream_only(page)
                return

        self._schedule_signals(page, delay_ms=0)
        self._schedule_positions(page, delay_ms=100)
        if hasattr(page, "end_tab_switch_loading"):
            page.end_tab_switch_loading()

    def _schedule_signals(self, page: WatchlistHost, *, delay_ms: int = 0) -> None:
        if not page.config.show_watchlist_signals:
            return
        QtCore.QTimer.singleShot(
            delay_ms,
            lambda: page._signals.on_stock_list_loaded() if page._active else None,
        )

    def _schedule_positions(self, page: WatchlistHost, *, delay_ms: int = 0) -> None:
        if not page.config.show_watchlist_positions:
            return
        QtCore.QTimer.singleShot(
            delay_ms,
            lambda: page._positions.on_stock_list_loaded() if page._active else None,
        )

    @staticmethod
    def _render_positions_only(page: WatchlistHost) -> None:
        if not page.config.show_watchlist_positions:
            return
        panel = getattr(page, "position_panel", None)
        if panel is not None:
            panel.render_panel()

    def _schedule_multiview(self, page: WatchlistHost, *, preset: LayoutPresetId) -> None:
        if not page.config.show_watchlist_multiview:
            return
        if preset == "intraday" and not page._multiview.is_multiview_active():
            return
        if preset == "review" and not page._multiview.is_multiview_active():
            return

        QtCore.QTimer.singleShot(
            0,
            lambda: page._multiview.on_stock_list_loaded() if page._active else None,
        )
