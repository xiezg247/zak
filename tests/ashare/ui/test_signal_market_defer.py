"""信号区表格与市场页延后更新。"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from unittest.mock import MagicMock, patch

import pytest
import tests._bootstrap  # noqa: F401
from vnpy.trader.ui import QtWidgets

from vnpy_ashare.ui.quotes.table.model import QuoteCell
from vnpy_ashare.ui.quotes.watchlist_signals.signal_panel_model import SignalPanelTableModel


@pytest.fixture(scope="module")
def qapp() -> QtWidgets.QApplication:
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app


def _cell(text: str) -> QuoteCell:
    return QuoteCell(text=text)


def test_reorder_symbols_keeps_rows_without_reset(qapp: QtWidgets.QApplication) -> None:
    model = SignalPanelTableModel()
    model.set_headers(["name"])
    model.set_rows_with_symbols(
        ["600000.SH", "000001.SZ"],
        [[_cell("a")], [_cell("b")]],
    )
    reset_calls: list[int] = []

    def _begin_reset() -> None:
        reset_calls.append(1)

    with patch.object(model, "beginResetModel", side_effect=_begin_reset):
        ok = model.reorder_symbols(["000001.SZ", "600000.SH"])

    assert ok is True
    assert reset_calls == []
    assert model.vt_symbol_at(0) == "000001.SZ"
    assert model._rows[0][0].text == "b"


def test_reorder_symbols_rejects_symbol_set_change(qapp: QtWidgets.QApplication) -> None:
    model = SignalPanelTableModel()
    model.set_rows_with_symbols(["600000.SH"], [[_cell("a")]])
    assert model.reorder_symbols(["000001.SZ"]) is False


def test_defer_when_market_idle_runs_immediately_when_not_paused(qapp: QtWidgets.QApplication) -> None:
    from vnpy_ashare.ui.quotes.page.quotes_page import QuotesPage

    class _Page:
        config = MagicMock(market_scroll_paging=True)

        def _market_background_sync_paused(self) -> bool:
            return False

    page = _Page()
    calls: list[int] = []

    QuotesPage._defer_when_market_idle(page, lambda: calls.append(1))
    assert calls == [1]


def test_defer_when_market_idle_retries_while_paused(qapp: QtWidgets.QApplication) -> None:
    from vnpy_ashare.ui.quotes.page.quotes_page import QuotesPage

    class _Page:
        config = MagicMock(market_scroll_paging=True)

        def __init__(self) -> None:
            self._paused = iter([True, False])

        def _market_background_sync_paused(self) -> bool:
            return next(self._paused, False)

    page = _Page()
    calls: list[int] = []

    QuotesPage._defer_when_market_idle(page, lambda: calls.append(1), retry_ms=100)
    assert calls == []

    QuotesPage._defer_when_market_idle(
        page,
        lambda: calls.append(1),
        retry_ms=100,
        attempt=1,
    )
    assert calls == [1]
