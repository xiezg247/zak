"""自选页信号区与持仓区联动。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vnpy_ashare.config.preferences.watchlist_position import WatchlistPositionConfig, save_watchlist_position_config
from vnpy_ashare.config.preferences.watchlist_signal import SIGNAL_PANEL_MAX_SYMBOLS
from vnpy_ashare.domain.symbols.stock import lookup_by_vt_symbol
from vnpy_ashare.ui.quotes.watchlist_signals.splitter import apply_center_splitter_sizes

if TYPE_CHECKING:
    from vnpy_ashare.ui.quotes.page.quotes_page import QuotesPage


class WatchlistPanelsFeature:
    """封装 QuotesPage 信号区 / 持仓区 wiring 与交互。"""

    def __init__(self, page: QuotesPage) -> None:
        self._page = page

    def wire_signal_panel(self) -> None:
        page = self._page
        panel = getattr(page, "signal_panel", None)
        if panel is None:
            return
        panel.symbols_changed.connect(page._signals.on_symbols_changed)
        panel.enabled_changed.connect(page._signals.on_panel_enabled_changed)
        panel.config_changed.connect(self.on_signal_panel_config_changed)
        panel.refresh_requested.connect(page.refresh_watchlist_signals)
        panel.row_activated.connect(self.on_signal_panel_row_activated)
        panel.row_selected.connect(self.on_signal_panel_row_activated)
        panel.expansion_changed.connect(self.on_signal_panel_expansion_changed)
        panel.ai_interpret_requested.connect(page._actions.ask_ai_for_signal_panel)
        panel.ai_scan_requested.connect(page._actions.ask_ai_for_signal_panel_batch)

    def wire_position_panel(self) -> None:
        page = self._page
        panel = getattr(page, "position_panel", None)
        if panel is None:
            return
        panel.rows_changed.connect(page._positions.on_rows_changed)
        panel.enabled_changed.connect(page._positions.on_panel_enabled_changed)
        panel.config_changed.connect(self.on_position_panel_config_changed)
        panel.refresh_requested.connect(page.refresh_watchlist_positions)
        panel.row_activated.connect(self.on_position_panel_row_activated)
        panel.row_selected.connect(self.on_position_panel_row_selected)
        panel.expansion_changed.connect(self.on_position_panel_expansion_changed)

    def on_signal_panel_expansion_changed(self, expanded: bool) -> None:
        apply_center_splitter_sizes(self._page)
        if expanded and self._page._signals._symbols_missing_cache(self._page._signals._panel_symbols()):
            self._page._signals.refresh(force=True)
        elif expanded:
            self._page._signals.refresh(force=False)

    def on_signal_panel_config_changed(self) -> None:
        page = self._page
        panel = getattr(page, "signal_panel", None)
        if panel is None:
            return
        page._signals.apply_config(panel.read_config())

    def apply_signal_panel_config(self) -> None:
        """应用信号区当前配置（构建 UI 期间也可安全调用）。"""
        self.on_signal_panel_config_changed()

    def on_signal_panel_row_activated(self, vt_symbol: str) -> None:
        page = self._page
        item = page.find_stock_item(vt_symbol)
        if item is None:
            return
        page._select_stock_key((item.symbol, item.exchange))
        snap = lookup_by_vt_symbol(page.signal_cache, vt_symbol)
        if snap is not None and page.chart_panel is not None:
            item = page.find_stock_item(vt_symbol)
            quote = page.quote_map.get(item.tickflow_symbol) if item is not None else None
            cfg = page.signal_config.normalized()
            page.chart_panel.apply_signal_reference(
                snap,
                quote=quote,
                fast_window=cfg.fast_window,
                slow_window=cfg.slow_window,
            )

    def on_position_panel_expansion_changed(self, _expanded: bool) -> None:
        apply_center_splitter_sizes(self._page)

    def on_position_panel_config_changed(self) -> None:
        page = self._page
        panel = getattr(page, "position_panel", None)
        if panel is None:
            return
        self.apply_position_config(panel.read_config())

    def apply_position_config(
        self,
        config: WatchlistPositionConfig,
        *,
        save: bool = True,
    ) -> None:
        page = self._page
        normalized = config.normalized()
        page.position_config = normalized
        if save:
            save_watchlist_position_config(normalized)
        panel = getattr(page, "position_panel", None)
        if panel is not None:
            panel.apply_config(normalized)
        if page.config.show_watchlist_positions:
            page._positions.invalidate_cache()
            page._positions.refresh(force=True)

    def on_position_panel_row_selected(self, vt_symbol: str) -> None:
        page = self._page
        item = page.find_stock_item(vt_symbol)
        if item is None:
            return
        page._select_stock_key((item.symbol, item.exchange))

    def on_position_panel_row_activated(self, vt_symbol: str) -> None:
        page = self._page
        self.on_position_panel_row_selected(vt_symbol)
        snap = page.position_cache.get(vt_symbol)
        if snap is not None and snap.signal_snapshot is not None and page.chart_panel is not None:
            item = page.find_stock_item(vt_symbol)
            quote = page.quote_map.get(item.tickflow_symbol) if item is not None else None
            pos_cfg = page.position_config.normalized().effective_signal_config(page.signal_config)
            page.chart_panel.apply_signal_reference(
                snap.signal_snapshot,
                quote=quote,
                fast_window=pos_cfg.fast_window,
                slow_window=pos_cfg.slow_window,
            )

    def add_selection_to_signal_panel(self) -> None:
        page = self._page
        panel = getattr(page, "signal_panel", None)
        if panel is None:
            return
        items = page._table.selected_items()
        if not items:
            page._toast.warning("请先在自选表中选择标的")
            return
        added, skipped = panel.add_symbols([item.vt_symbol for item in items])
        if added:
            message = f"已加入信号区 {added} 只"
            if skipped:
                message += f"，{skipped} 只因已达上限 {SIGNAL_PANEL_MAX_SYMBOLS} 未加入"
            page._toast.success(message)
            page._signals.refresh(force=True)
        elif skipped:
            page._toast.warning(f"信号区已满（最多 {SIGNAL_PANEL_MAX_SYMBOLS} 只），请先移出后再加入")
        else:
            page._toast.info("所选标的已在信号区")
