"""A 股终端：AI 助手内标的跳转实现。"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, cast

from vnpy.trader.constant import Exchange
from vnpy.event import Event
from vnpy.trader.ui import QtCore

from vnpy_ashare.ai.context.symbol import parse_stock_symbol
from vnpy_ashare.ai.context.team_symbol import normalize_symbol_code, resolve_team_symbol
from vnpy_ashare.app.engine_access import get_watchlist_service
from vnpy_ashare.app.events import EVENT_OPEN_BACKTEST, BacktestRequest
from vnpy_ashare.config.runtime import exchange_to_cn
from vnpy_ashare.domain.symbols.stock import StockItem
from vnpy_ashare.storage.repositories.watchlist import watchlist_contains
from vnpy_ashare.ui.features.notes_center.open import show_notes_center_dialog
from vnpy_ashare.ui.features.notes_center.save_from_ai import (
    ContextStock,
    save_message_as_journal,
    save_message_as_report,
    save_recent_turns_as_journal,
    save_recent_turns_as_report,
)
from vnpy_common.ai.access import get_ai_context
from vnpy_ashare.ui.features.stock_analysis.host import StockAnalysisHost
from vnpy_ashare.ui.features.stock_analysis.open import show_stock_analysis_vt_symbol
from vnpy_ashare.ui.screener.dialogs.reference_peer_dialog import show_reference_peer_dialog
from vnpy_common.ai.protocol import StockCompletionItem, SymbolRef
from vnpy_common.ai.symbol_navigation import SymbolNavigationPort


def _normalize_vt(vt_symbol: str) -> str:
    item = parse_stock_symbol(vt_symbol)
    if item is not None:
        return item.vt_symbol
    return vt_symbol


def _to_ref(item: StockItem) -> SymbolRef:
    return SymbolRef(
        symbol=item.symbol,
        exchange=item.exchange.name,
        name=item.name,
        vt_symbol=item.vt_symbol,
    )


class AshareSymbolNavigation:
    """vnpy_ashare 侧 SymbolNavigationPort 实现。"""

    def parse(self, vt_symbol: str, *, name: str = "") -> SymbolRef | None:
        normalized = _normalize_vt(vt_symbol) or vt_symbol
        item = parse_stock_symbol(normalized)
        if item is None:
            return None
        if name and not item.name:
            item = StockItem(symbol=item.symbol, exchange=item.exchange, name=name)
        return _to_ref(item)

    def normalize_vt_symbol(self, raw: str) -> str | None:
        return normalize_symbol_code(raw)

    def resolve_team_symbol(
        self,
        *,
        user_text: str,
        context_symbol: str = "",
        context_exchange: str = "",
    ) -> str | None:
        return resolve_team_symbol(
            user_text=user_text,
            context_symbol=context_symbol,
            context_exchange=context_exchange,
        )

    def resolve_context_symbol(self) -> SymbolRef | None:
        data = get_ai_context()
        symbol = str(data.symbol or "").strip()
        exchange = str(data.exchange or "").strip()
        if not symbol or not exchange:
            return None
        if exchange not in Exchange.__members__:
            return None
        return SymbolRef(
            symbol=symbol,
            exchange=exchange,
            name=str(data.name or "").strip(),
            vt_symbol=f"{symbol}.{exchange}",
        )

    def watchlist_contains(self, item: SymbolRef) -> bool:
        stock = parse_stock_symbol(item.vt_symbol)
        if stock is None:
            return False
        return watchlist_contains(stock.symbol, stock.exchange)

    def open_analysis(
        self,
        item: SymbolRef,
        *,
        main_engine: Any,
        event_engine: Any,
        parent: Any,
    ) -> None:
        host = StockAnalysisHost.from_main_engine(
            main_engine,
            event_engine=event_engine,
            source_page="AI 助手",
        )
        show_stock_analysis_vt_symbol(
            item.vt_symbol,
            host,
            name=item.name,
            parent=parent,
            modality=QtCore.Qt.WindowModality.NonModal,
        )

    def focus_watchlist(self, item: SymbolRef, *, host: Any) -> bool:
        if host is not None and hasattr(host, "focus_watchlist_symbol"):
            host.focus_watchlist_symbol(item.symbol, item.exchange)
            return True
        return False

    def open_backtest(self, item: SymbolRef, *, event_engine: Any) -> None:
        event_engine.put(
            Event(
                EVENT_OPEN_BACKTEST,
                BacktestRequest(vt_symbol=item.vt_symbol, source_page="AI 助手", name=item.name),
            ),
        )

    def toggle_watchlist(self, item: SymbolRef, *, main_engine: Any) -> str:
        """返回 notify level：success / info / warning / error。"""
        service = get_watchlist_service(main_engine)
        if service is None:
            return "error:自选服务未就绪"
        stock = parse_stock_symbol(item.vt_symbol)
        if stock is None:
            return "error:无法解析标的"
        if watchlist_contains(stock.symbol, stock.exchange):
            if service.remove(stock.symbol, stock.exchange):
                return f"success:已移出自选：{item.vt_symbol}"
            return "warning:移出自选失败"
        reason = service.add_failure_reason(stock.symbol, stock.exchange)
        if reason == "duplicate":
            return f"info:已在自选中：{item.vt_symbol}"
        if reason == "full":
            return "warning:自选池已满"
        if service.add(stock.symbol, stock.exchange, stock.name):
            return f"success:已加入自选：{item.vt_symbol}"
        return "warning:加入自选失败"

    def open_reference_peer(self, item: SymbolRef, *, main_engine: Any, parent: Any) -> None:
        service = get_watchlist_service(main_engine)

        def watchlist_add(symbol: str, exchange, stock_name: str = "") -> bool:
            if service is None:
                return False
            return cast(bool, service.add(symbol, exchange, stock_name))

        show_reference_peer_dialog(
            vt_symbol=item.vt_symbol,
            reference_name=item.name,
            watchlist_add=watchlist_add if service is not None else None,
            parent=parent,
        )

    def open_team_report(
        self,
        *,
        report_id: int,
        vt_symbol: str,
        main_engine: Any,
        event_engine: Any,
        parent: Any,
    ) -> None:
        show_notes_center_dialog(
            main_engine,
            event_engine,
            initial_vt_symbol=vt_symbol,
            initial_tab="reports",
            parent=parent,
        )

    def build_completion_items(self, item: SymbolRef) -> list[StockCompletionItem]:
        from vnpy_ashare.ai.context.quote.assembly import build_stock_completion_items

        stock = parse_stock_symbol(item.vt_symbol)
        if stock is None:
            return []
        return [
            StockCompletionItem(label=entry.label, prompt=entry.prompt)
            for entry in build_stock_completion_items(
                stock.symbol,
                exchange_cn=exchange_to_cn(stock.exchange),
                name=stock.name,
            )
        ]

    def save_report(self, *, main_engine: Any, text: str, item: SymbolRef, parent: Any) -> bool:
        stock = ContextStock(symbol=item.symbol, exchange=item.exchange, name=item.name)
        return save_message_as_report(main_engine, text, parent=parent, stock=stock)

    def save_journal(self, *, main_engine: Any, text: str, item: SymbolRef) -> bool:
        stock = ContextStock(symbol=item.symbol, exchange=item.exchange, name=item.name)
        return save_message_as_journal(main_engine, text, stock=stock)

    def save_recent_turns_as_report(
        self,
        *,
        main_engine: Any,
        messages: Sequence[Any],
        turn_count: int,
        parent: Any,
        item: SymbolRef | None = None,
    ) -> bool:
        stock = self._context_stock(item) if item is not None else None
        return save_recent_turns_as_report(
            main_engine,
            messages,
            turn_count=turn_count,
            parent=parent,
            stock=stock,
        )

    def save_recent_turns_as_journal(
        self,
        *,
        main_engine: Any,
        messages: Sequence[Any],
        turn_count: int,
        item: SymbolRef | None = None,
    ) -> bool:
        stock = self._context_stock(item) if item is not None else None
        return save_recent_turns_as_journal(
            main_engine,
            messages,
            turn_count=turn_count,
            stock=stock,
        )

    @staticmethod
    def _context_stock(item: SymbolRef) -> ContextStock:
        return ContextStock(symbol=item.symbol, exchange=item.exchange, name=item.name)


def build_ashare_symbol_navigation() -> SymbolNavigationPort:
    return AshareSymbolNavigation()
