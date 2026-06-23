"""自选页加载编排：池同步、下游刷新去重、预设感知调度。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from vnpy.trader.ui import QtCore

from vnpy_ashare.domain.symbols.stock import StockItem
from vnpy_ashare.ui.quotes.features.watchlist.prefs import LayoutPresetId, load_watchlist_layout_preset

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
        if page.page_name != "自选":
            page.load_stock_list()
            return

        pool = page._watchlist._pool_from_service()
        fingerprint = self.pool_fingerprint(pool)
        if self._last_pool_fingerprint is not None and fingerprint == self._last_pool_fingerprint and page.display_stocks:
            self._sync_display_only(page, pool)
            self.schedule_downstream(page, reason="tab_resume")
            return

        page.load_stock_list()

    def on_pool_ready(
        self,
        page: WatchlistHost,
        stocks: list[StockItem],
        *,
        source: ScheduleReason,
    ) -> None:
        if page.page_name != "自选":
            return

        self._last_pool_fingerprint = self.pool_fingerprint(stocks)
        page.watchlist_pool_stocks = list(stocks)

        if page._watchlist_groups is not None:
            page._watchlist_groups.on_stock_list_loaded(stocks)
        else:
            page.all_stocks = list(stocks)
            page.apply_filter()

        page._watchlist.refresh_keys()
        feature = getattr(page, "_watchlist_feature", None)
        if feature is not None:
            feature.on_stock_list_loaded()

        page._update_action_buttons()
        self.schedule_downstream(page, reason=source)

    def schedule_downstream(self, page: WatchlistHost, *, reason: ScheduleReason) -> None:
        if page.page_name != "自选" or not page._active:
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
        page.watchlist_pool_stocks = list(pool)
        if page._watchlist_groups is not None:
            page._watchlist_groups.on_stock_list_loaded(pool)
        else:
            page.all_stocks = list(pool)
            page.apply_filter()
        page._watchlist.refresh_keys()
        feature = getattr(page, "_watchlist_feature", None)
        if feature is not None:
            feature.refresh_context_bar()
        page._update_action_buttons()

    def _run_downstream(self, page: WatchlistHost, *, reason: ScheduleReason) -> None:
        preset = load_watchlist_layout_preset()

        if preset == "intraday":
            self._schedule_signals(page)
            self._render_positions_only(page)
        elif preset == "register":
            self._schedule_signals(page)
            self._schedule_positions(page)
        elif preset == "review":
            self._schedule_positions(page)
            QtCore.QTimer.singleShot(100, lambda: self._schedule_signals(page))

        self._schedule_multiview(page, preset=preset)

    def _schedule_signals(self, page: WatchlistHost) -> None:
        if page.config.show_watchlist_signals:
            page._signals.on_stock_list_loaded()

    def _schedule_positions(self, page: WatchlistHost) -> None:
        if page.config.show_watchlist_positions:
            page._positions.on_stock_list_loaded()

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

        def _load() -> None:
            if page._active:
                page._multiview.on_stock_list_loaded()

        if preset == "register" and page._multiview.is_multiview_active():
            QtCore.QTimer.singleShot(100, _load)
        else:
            _load()
