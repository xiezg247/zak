"""自选页列表行情加载状态栏标识。"""

from __future__ import annotations

from unittest.mock import MagicMock

import tests._bootstrap  # noqa: F401


def _make_watchlist_page(*, quote_map: dict | None = None) -> MagicMock:
    from vnpy_ashare.ui.quotes.page.roles import WATCHLIST_PAGE
    from vnpy_ashare.ui.quotes.watchlist.quote_status import (
        LOADING_SUFFIX,
        append_loading_suffix,
        begin_watchlist_quotes_fetch,
        display_quotes_pending,
        end_watchlist_quotes_fetch,
        should_show_quotes_loading,
    )

    page = MagicMock()
    page.page_name = WATCHLIST_PAGE
    page.config.scope_key = "自选池"
    page.config.use_quote_stream = True
    page._active = True
    page._watchlist_quotes_loading = False
    page.quote_map = quote_map or {}
    page.display_stocks = [MagicMock(tickflow_symbol="600000.SH")]
    page.status_label = MagicMock()
    page._table = MagicMock()
    page._table.update_display_status = MagicMock()

    page._helpers = {
        "LOADING_SUFFIX": LOADING_SUFFIX,
        "append_loading_suffix": append_loading_suffix,
        "begin_watchlist_quotes_fetch": begin_watchlist_quotes_fetch,
        "display_quotes_pending": display_quotes_pending,
        "end_watchlist_quotes_fetch": end_watchlist_quotes_fetch,
        "should_show_quotes_loading": should_show_quotes_loading,
    }
    return page


def test_should_show_loading_when_rest_fetch_active() -> None:
    page = _make_watchlist_page(quote_map={"600000.SH": object()})
    page.config.use_quote_stream = False
    h = page._helpers

    assert h["should_show_quotes_loading"](page) is False

    h["begin_watchlist_quotes_fetch"](page)
    assert h["should_show_quotes_loading"](page) is True
    assert h["append_loading_suffix"](page, "自选  匹配 1 只") == f"自选  匹配 1 只{h['LOADING_SUFFIX']}"


def test_should_show_loading_when_stream_quotes_pending() -> None:
    page = _make_watchlist_page()
    h = page._helpers

    assert h["display_quotes_pending"](page) is True
    assert h["should_show_quotes_loading"](page) is True

    page.quote_map = {"600000.SH": object()}
    assert h["display_quotes_pending"](page) is False
    assert h["should_show_quotes_loading"](page) is False


def test_end_fetch_restores_status_via_table() -> None:
    page = _make_watchlist_page()
    h = page._helpers
    h["begin_watchlist_quotes_fetch"](page)
    h["end_watchlist_quotes_fetch"](page)

    assert page._watchlist_quotes_loading is False
    assert page._table.update_display_status.call_count == 2


def test_loading_suffix_skipped_for_non_watchlist_page() -> None:
    page = _make_watchlist_page()
    h = page._helpers
    page.page_name = "市场"
    page._watchlist_quotes_loading = True

    assert h["append_loading_suffix"](page, "市场  匹配 10 只") == "市场  匹配 10 只"
