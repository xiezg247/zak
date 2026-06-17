"""QuoteStreamController 图表行情 debounce 测试。"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from PySide6.QtTest import QTest
from vnpy.trader.constant import Exchange
from vnpy.trader.ui import QtWidgets

import tests._bootstrap  # noqa: F401
from vnpy_ashare.domain.symbols import StockItem
from vnpy_ashare.domain.market.quote_snapshot import QuoteSnapshot
from vnpy_ashare.ui.quotes.controllers.quote_stream import QuoteStreamController
from vnpy_ashare.ui.quotes.page.config import STREAM_CHART_QUOTE_DEBOUNCE_MS


def _sample_quote() -> QuoteSnapshot:
    return QuoteSnapshot(
        symbol="600519.SH",
        name="贵州茅台",
        last_price=1800.0,
        prev_close=1790.0,
        open_price=1795.0,
        high_price=1810.0,
        low_price=1788.0,
        change_amount=10.0,
        change_pct=0.56,
        turnover_rate=0.2,
        volume=10000.0,
    )


class QuoteStreamChartDebounceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def _make_controller(self) -> tuple[QuoteStreamController, MagicMock, MagicMock, StockItem]:
        host = QtWidgets.QWidget()
        page = MagicMock()
        page._active = True
        page.config.show_watchlist_positions = False
        page.quote_map = {}
        item = StockItem(symbol="600519", exchange=Exchange.SSE, name="茅台")
        page.current_item = item
        chart_panel = MagicMock()
        page.chart_panel = chart_panel
        page._table = MagicMock()
        page._actions = MagicMock()
        controller = QuoteStreamController(host)
        controller._page = page
        controller._host = host  # 保持 timer 父对象存活
        return controller, page, chart_panel, item

    def test_flush_quotes_defers_chart_update(self) -> None:
        controller, page, chart_panel, item = self._make_controller()
        quote = _sample_quote()
        page.quote_map[item.tickflow_symbol] = quote
        controller._pending_symbols = {item.tickflow_symbol}

        controller._flush_quotes()

        chart_panel.update_quote.assert_not_called()
        page._update_quote_header.assert_called_once_with(item)

    def test_chart_quote_timer_flushes_latest_quote(self) -> None:
        controller, page, chart_panel, item = self._make_controller()
        quote = _sample_quote()
        page.quote_map[item.tickflow_symbol] = quote

        controller._schedule_chart_quote_update()
        QTest.qWait(STREAM_CHART_QUOTE_DEBOUNCE_MS + 30)

        chart_panel.update_quote.assert_called_once_with(quote)

    def test_repeated_schedule_coalesces_chart_updates(self) -> None:
        controller, page, chart_panel, item = self._make_controller()
        quote = _sample_quote()
        page.quote_map[item.tickflow_symbol] = quote

        controller._schedule_chart_quote_update()
        controller._schedule_chart_quote_update()
        QTest.qWait(STREAM_CHART_QUOTE_DEBOUNCE_MS + 30)

        chart_panel.update_quote.assert_called_once()


if __name__ == "__main__":
    unittest.main()
