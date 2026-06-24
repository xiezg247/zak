"""AI 助手内标的跳转桥：vnpy_ashare 注册实现，vnpy_llm 只读。"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Protocol, runtime_checkable

from vnpy_common.ai.protocol import StockCompletionItem, SymbolRef, WatchlistToggleResult


@runtime_checkable
class SymbolNavigationPort(Protocol):
    def parse(self, vt_symbol: str, *, name: str = "") -> SymbolRef | None: ...

    def normalize_vt_symbol(self, raw: str) -> str | None: ...

    def resolve_team_symbol(
        self,
        *,
        user_text: str,
        context_symbol: str = "",
        context_exchange: str = "",
    ) -> str | None: ...

    def resolve_context_symbol(self) -> SymbolRef | None: ...

    def watchlist_contains(self, item: SymbolRef) -> bool: ...

    def open_analysis(
        self,
        item: SymbolRef,
        *,
        main_engine: Any,
        event_engine: Any,
        parent: Any,
    ) -> None: ...

    def focus_watchlist(self, item: SymbolRef, *, host: Any) -> bool: ...

    def open_backtest(self, item: SymbolRef, *, event_engine: Any) -> None: ...

    def toggle_watchlist(self, item: SymbolRef, *, main_engine: Any) -> WatchlistToggleResult: ...

    def open_reference_peer(self, item: SymbolRef, *, main_engine: Any, parent: Any) -> None: ...

    def open_team_report(
        self,
        *,
        report_id: int,
        vt_symbol: str,
        main_engine: Any,
        event_engine: Any,
        parent: Any,
    ) -> None: ...

    def build_completion_items(self, item: SymbolRef) -> list[StockCompletionItem]: ...

    def save_report(
        self,
        *,
        main_engine: Any,
        text: str,
        item: SymbolRef,
        parent: Any,
        charts: Sequence[Any] | None = None,
    ) -> bool: ...

    def save_journal(self, *, main_engine: Any, text: str, item: SymbolRef) -> bool: ...

    def save_recent_turns_as_report(
        self,
        *,
        main_engine: Any,
        messages: Sequence[Any],
        turn_count: int,
        parent: Any,
        item: SymbolRef | None = None,
        charts: Sequence[Any] | None = None,
    ) -> bool: ...

    def save_recent_turns_as_journal(
        self,
        *,
        main_engine: Any,
        messages: Sequence[Any],
        turn_count: int,
        item: SymbolRef | None = None,
    ) -> bool: ...


_symbol_navigation: SymbolNavigationPort | None = None


def register_symbol_navigation(port: SymbolNavigationPort) -> None:
    global _symbol_navigation
    _symbol_navigation = port


def get_symbol_navigation() -> SymbolNavigationPort | None:
    return _symbol_navigation
