"""TickFlow WebSocket 行情/五档推送桥接（Qt 信号）。"""

from __future__ import annotations

import importlib.util
import logging
import os
import threading
import urllib.request
import weakref
from typing import TYPE_CHECKING

from vnpy.trader.ui import QtCore

from vnpy_ashare.integrations.tickflow.quotes import get_tickflow_client, parse_quote_row
from vnpy_ashare.quotes.core.depth_snapshot import DepthSnapshot
from vnpy_ashare.quotes.core.enrich import fill_missing_tushare_factors
from vnpy_ashare.quotes.core.snapshot import QuoteSnapshot

if TYPE_CHECKING:
    from tickflow.resources.stream import MarketStream

_logger = logging.getLogger(__name__)

_PROXY_ENV_KEYS = (
    "ALL_PROXY",
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "all_proxy",
    "http_proxy",
    "https_proxy",
)


def _iter_proxy_urls() -> list[str]:
    urls: list[str] = []
    for key in _PROXY_ENV_KEYS:
        value = os.environ.get(key, "").strip()
        if value:
            urls.append(value)
    try:
        for value in urllib.request.getproxies().values():
            if value:
                urls.append(str(value))
    except Exception:
        pass
    return urls


def can_use_tickflow_stream() -> bool:
    """SOCKS 代理环境下需 python-socks，否则 WebSocket 会无限重连。"""
    if importlib.util.find_spec("python_socks") is not None:
        return True
    try:
        if urllib.request.getproxies().get("socks"):
            return False
    except Exception:
        pass
    for proxy_url in _iter_proxy_urls():
        lowered = proxy_url.lower()
        if lowered.startswith("socks") or lowered.startswith("socks5") or lowered.startswith("socks4"):
            return False
    return True


_STREAM_SHUTDOWN_JOIN_TIMEOUT_SEC = 3.0
_active_bridges: weakref.WeakSet = weakref.WeakSet()
_market_stream_shutdown_patched = False


def _patch_market_stream_shutdown() -> None:
    """修补 tickflow MarketStream：退出时标记 closed 并等待后台线程结束。"""
    global _market_stream_shutdown_patched
    if _market_stream_shutdown_patched:
        return
    try:
        from tickflow.resources.stream import MarketStream
    except ImportError:
        return

    original_close = MarketStream.close
    original_run_in_thread = MarketStream._run_in_thread

    def patched_close(self: MarketStream) -> None:
        self._stop.set()
        inner = getattr(self, "_inner", None)
        if inner is not None:
            inner._closed = True
        original_close(self)
        thread = getattr(self, "_thread", None)
        if thread is not None and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=_STREAM_SHUTDOWN_JOIN_TIMEOUT_SEC)

    def patched_run_in_thread(self: MarketStream) -> None:
        try:
            original_run_in_thread(self)
        except RuntimeError as ex:
            if "interpreter shutdown" in str(ex).lower():
                _logger.debug("TickFlow stream thread ended during interpreter shutdown")
                return
            raise

    MarketStream.close = patched_close
    MarketStream._run_in_thread = patched_run_in_thread
    _market_stream_shutdown_patched = True


def shutdown_all_tickflow_streams() -> None:
    """应用退出前关闭所有活跃 WebSocket 桥接（避免解释器收尾时后台线程仍运行）。"""
    for bridge in list(_active_bridges):
        try:
            bridge.stop()
        except Exception:
            _logger.debug("TickFlow bridge stop failed during app shutdown", exc_info=True)


_patch_market_stream_shutdown()


class TickflowStreamBridge(QtCore.QObject):
    """后台 WebSocket 线程 → 主线程 Qt 信号。"""

    quotes_updated = QtCore.Signal(object)
    depth_updated = QtCore.Signal(object)
    depth_permission_denied = QtCore.Signal(str)
    connected = QtCore.Signal()
    disconnected = QtCore.Signal()
    error = QtCore.Signal(str)

    def __init__(self, parent: QtCore.QObject | None = None) -> None:
        super().__init__(parent)
        self._stream: MarketStream | None = None
        self._quote_symbols: set[str] = set()
        self._depth_symbol: str | None = None
        self._connected = False
        self._depth_denied = False
        self._disabled = False
        _active_bridges.add(self)

    @property
    def is_connected(self) -> bool:
        return self._connected and not self._disabled

    @property
    def depth_denied(self) -> bool:
        return self._depth_denied

    def start(self) -> None:
        if self._stream is not None or self._disabled:
            return

        client = get_tickflow_client()
        stream = client.stream

        @stream.on_quotes
        def on_quotes(rows: list[dict]) -> None:
            if not rows:
                return
            if not self._connected:
                self._connected = True
                self.connected.emit()
            quotes: dict[str, QuoteSnapshot] = {}
            for row in rows:
                quote = parse_quote_row(row)
                quotes[quote.symbol] = quote
            fill_missing_tushare_factors(quotes)
            self.quotes_updated.emit(quotes)

        @stream.on_depth
        def on_depth(rows: list[dict]) -> None:
            if not rows:
                return
            for row in rows:
                self.depth_updated.emit(DepthSnapshot.from_tickflow(row))

        @stream.on_error
        def on_error(message: str) -> None:
            self._handle_stream_error(message)

        self._stream = stream
        if self._quote_symbols:
            stream.subscribe("quotes", sorted(self._quote_symbols))
        if self._depth_symbol and not self._depth_denied:
            stream.subscribe("depth", [self._depth_symbol])
        stream.connect(block=False)

    def stop(self) -> None:
        self._shutdown_stream()
        self._mark_disconnected()

    @staticmethod
    def _is_fatal_error(message: str) -> bool:
        lowered = message.lower()
        if "python-socks" in lowered or "socks proxy" in lowered:
            return True
        if "401" in message or "404" in message:
            return True
        return "403" in message and "depth" not in lowered

    def _handle_stream_error(self, message: str) -> None:
        lowered = message.lower()
        if "403" in message and "depth" in lowered:
            self._depth_denied = True
            self.depth_permission_denied.emit(message)
            return

        self._mark_disconnected()
        self.error.emit(message)
        if self._is_fatal_error(message):
            self._disabled = True
            self._shutdown_stream()

    def _shutdown_stream(self) -> None:
        stream = self._stream
        self._stream = None
        if stream is None:
            return
        self._disabled = True
        inner = getattr(stream, "_inner", None)
        if inner is not None:
            inner._closed = True
        try:
            stream.close()
        except Exception:
            _logger.debug("TickFlow stream close failed", exc_info=True)
        thread = getattr(stream, "_thread", None)
        if thread is not None and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=_STREAM_SHUTDOWN_JOIN_TIMEOUT_SEC)

    def set_quote_symbols(self, symbols: list[str]) -> None:
        new_set = {symbol for symbol in symbols if symbol}
        if new_set == self._quote_symbols:
            return

        to_add = sorted(new_set - self._quote_symbols)
        to_remove = sorted(self._quote_symbols - new_set)
        self._quote_symbols = new_set

        if self._stream is None:
            return
        if to_remove:
            self._stream.unsubscribe("quotes", to_remove)
        if to_add:
            self._stream.subscribe("quotes", to_add)

    def set_depth_symbol(self, symbol: str | None) -> None:
        symbol = symbol or None
        if symbol == self._depth_symbol:
            return

        previous = self._depth_symbol
        self._depth_symbol = symbol
        if self._stream is None or self._depth_denied:
            return
        if previous:
            self._stream.unsubscribe("depth", [previous])
        if symbol:
            self._stream.subscribe("depth", [symbol])

    def _mark_disconnected(self) -> None:
        if not self._connected:
            return
        self._connected = False
        self.disconnected.emit()
