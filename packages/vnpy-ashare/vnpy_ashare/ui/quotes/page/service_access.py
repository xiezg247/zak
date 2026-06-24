"""QuotesPage 经 MainEngine 访问 Service 的薄封装。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from vnpy_ashare.app.engine_access import (
    get_analysis_service,
    get_bar_service,
    get_note_service,
    get_position_service,
    get_quote_service,
    get_watchlist_service,
)
from vnpy_ashare.services.analysis import AnalysisService
from vnpy_ashare.services.note import NoteService
from vnpy_ashare.services.position import PositionService
from vnpy_ashare.services.watchlist import WatchlistService

if TYPE_CHECKING:
    from vnpy_ashare.ui.quotes.page.quotes_page import QuotesPage


def get_main_engine_for_page(page: QuotesPage) -> Any:
    parent = page.parent()
    if parent is not None and hasattr(parent, "main_engine"):
        return parent.main_engine
    return None


def get_watchlist_service_for_page(page: QuotesPage) -> WatchlistService | None:
    return get_watchlist_service(get_main_engine_for_page(page))


def get_position_service_for_page(page: QuotesPage) -> PositionService | None:
    return get_position_service(get_main_engine_for_page(page))


def get_note_service_for_page(page: QuotesPage) -> NoteService | None:
    return get_note_service(get_main_engine_for_page(page))


def get_analysis_service_for_page(page: QuotesPage) -> AnalysisService | None:
    return get_analysis_service(get_main_engine_for_page(page))


def get_quote_service_for_page(page: QuotesPage) -> Any:
    return get_quote_service(get_main_engine_for_page(page))


def get_bar_service_for_page(page: QuotesPage) -> Any:
    return get_bar_service(get_main_engine_for_page(page))
