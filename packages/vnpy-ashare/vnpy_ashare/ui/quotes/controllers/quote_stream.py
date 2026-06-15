"""TickFlow WebSocket 行情流控制器。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vnpy.trader.ui import QtCore

from vnpy_ashare.integrations.tickflow import TickflowStreamBridge, can_use_tickflow_stream
from vnpy_ashare.quotes.core.depth_snapshot import DepthSnapshot
from vnpy_ashare.ui.quotes.page.config import (
    STREAM_CHART_QUOTE_DEBOUNCE_MS,
    STREAM_QUOTE_DEBOUNCE_MS,
)

if TYPE_CHECKING:
    from vnpy_ashare.ui.quotes.page.quotes_page import QuotesPage


class QuoteStreamController:
    """自选页 WebSocket 行情/五档订阅。"""

    def __init__(self, page: QuotesPage) -> None:
        self._page = page
        self._pending_symbols: set[str] = set()
        self._flush_timer = QtCore.QTimer(page)
        self._flush_timer.setSingleShot(True)
        self._flush_timer.setInterval(STREAM_QUOTE_DEBOUNCE_MS)
        self._flush_timer.timeout.connect(self._flush_quotes)
        self._chart_quote_timer = QtCore.QTimer(page)
        self._chart_quote_timer.setSingleShot(True)
        self._chart_quote_timer.setInterval(STREAM_CHART_QUOTE_DEBOUNCE_MS)
        self._chart_quote_timer.timeout.connect(self._flush_chart_quote)

    def use_stream(self) -> bool:
        page = self._page
        return page.config.use_quote_stream and page._stream_bridge is not None and page._stream_bridge.is_connected and not page._stream_fallback

    def start(self) -> None:
        page = self._page
        if page._stream_bridge is not None:
            return
        if not can_use_tickflow_stream():
            page._stream_fallback = True
            page._update_quote_source_label()
            return
        bridge = TickflowStreamBridge(page)
        bridge.quotes_updated.connect(self.on_quotes)
        bridge.depth_updated.connect(self.on_depth)
        bridge.depth_permission_denied.connect(self.on_depth_denied)
        bridge.connected.connect(self._on_connected)
        bridge.disconnected.connect(self.on_disconnected)
        bridge.error.connect(self.on_error)
        page._stream_bridge = bridge
        page._stream_fallback = False
        bridge.start()
        page._update_quote_source_label()

    def stop(self) -> None:
        page = self._page
        self._flush_timer.stop()
        self._chart_quote_timer.stop()
        self._pending_symbols.clear()
        bridge = page._stream_bridge
        page._stream_bridge = None
        if bridge is None:
            return
        bridge.stop()
        bridge.deleteLater()

    def sync_subscriptions(self) -> None:
        page = self._page
        if page._stream_bridge is None:
            return
        symbols = [item.tickflow_symbol for item in page.display_stocks]
        page._stream_bridge.set_quote_symbols(symbols)
        self.sync_depth_subscription()

    def sync_depth_subscription(self) -> None:
        page = self._page
        if page._stream_bridge is None:
            return
        if page._depth_permission_denied or page.current_item is None:
            page._stream_bridge.set_depth_symbol(None)
            return
        page._stream_bridge.set_depth_symbol(page.current_item.tickflow_symbol)

    def _on_connected(self) -> None:
        page = self._page
        page._stream_fallback = False
        page._update_quote_source_label()

    def on_quotes(self, quotes: dict) -> None:
        page = self._page
        if not page._active:
            return
        page._stream_fallback = False
        page._update_quote_source_label()
        page.quote_map.update(quotes)
        self._pending_symbols.update(quotes.keys())
        self._flush_timer.start()

    def _flush_quotes(self) -> None:
        page = self._page
        if not page._active:
            self._pending_symbols.clear()
            return

        symbols = self._pending_symbols
        self._pending_symbols = set()
        if not symbols:
            return

        page._table.refresh_table_quotes_for_symbols(symbols)
        if page.config.show_watchlist_positions:
            page._positions.refresh_quotes_only()
        current = page.current_item
        if current is None or current.tickflow_symbol not in symbols:
            page._actions.schedule_ai_context()
            return
        page._update_quote_header(current)
        self._schedule_chart_quote_update()
        page._actions.schedule_ai_context()

    def _schedule_chart_quote_update(self) -> None:
        if self._page.chart_panel is None:
            return
        self._chart_quote_timer.start()

    def _flush_chart_quote(self) -> None:
        page = self._page
        if not page._active or page.chart_panel is None:
            return
        current = page.current_item
        if current is None:
            return
        quote = page.quote_map.get(current.tickflow_symbol)
        page.chart_panel.update_quote(quote)

    def on_depth(self, depth: DepthSnapshot) -> None:
        page = self._page
        if not page._active or page.depth_panel is None or page.current_item is None:
            return
        if depth.symbol != page.current_item.tickflow_symbol:
            return
        page.depth_panel.update_depth(depth)

    def on_depth_denied(self, _message: str) -> None:
        page = self._page
        page._depth_permission_denied = True
        if page.depth_panel is not None:
            page.depth_panel.show_permission_denied("未开通市场深度权限")
        self.sync_depth_subscription()

    def on_disconnected(self) -> None:
        page = self._page
        page._stream_fallback = True
        page._update_quote_source_label()

    def on_error(self, _message: str) -> None:
        page = self._page
        page._stream_fallback = True
        page._update_quote_source_label()
        self.stop()
        if page._active:
            page._refresh_quotes_rest()
