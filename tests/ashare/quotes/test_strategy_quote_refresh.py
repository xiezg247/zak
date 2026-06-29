"""策略监控页：关注池行情刷新与信号区现价列。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from vnpy.trader.constant import Exchange

import tests._bootstrap  # noqa: F401
from vnpy_ashare.domain.market.quote_snapshot import QuoteSnapshot
from vnpy_ashare.domain.symbols.stock import StockItem
from vnpy_ashare.ui.quotes.page.config import PAGE_CONFIGS, WATCHLIST_QUOTE_REFRESH_MS
from vnpy_ashare.ui.quotes.page.quote_refresh import quote_refresh_stock_items
from vnpy_ashare.ui.quotes.page.roles import STRATEGY_MONITOR_PAGE
from vnpy_ashare.ui.quotes.watchlist_signals.table_view import _compute_row_values


def test_strategy_monitor_page_auto_refresh_enabled() -> None:
    config = PAGE_CONFIGS[STRATEGY_MONITOR_PAGE]
    assert config.auto_refresh_quotes is True
    assert config.quote_refresh_ms == WATCHLIST_QUOTE_REFRESH_MS


@patch("vnpy_ashare.services.focus_pool.load_focus_pool_stock_items")
def test_quote_refresh_stock_items_uses_focus_pool_on_strategy_page(mock_load: MagicMock) -> None:
    items = [StockItem(symbol="600000", exchange=Exchange.SSE, name="浦发银行")]
    mock_load.return_value = items
    page = MagicMock()
    page.page_name = STRATEGY_MONITOR_PAGE

    result = quote_refresh_stock_items(page)

    assert result == items
    mock_load.assert_called_once()


def test_compute_row_values_shows_last_price_from_quote() -> None:
    item = StockItem(symbol="600000", exchange=Exchange.SSE, name="浦发银行")
    quote = QuoteSnapshot(
        symbol="600000",
        name="浦发银行",
        last_price=10.25,
        prev_close=10.12,
        open_price=10.15,
        high_price=10.30,
        low_price=10.10,
        change_amount=0.13,
        change_pct=1.23,
        turnover_rate=1.0,
        volume=1000.0,
    )
    panel_columns = (("symbol", "代码"), ("name", "名称"), ("last_price", "现价"), ("change_pct", "涨幅%"))

    values = _compute_row_values(
        item,
        None,
        quote,
        bar_end_date=None,
        config=MagicMock(),
        panel_columns=panel_columns,
    )

    assert values["last_price"] == "10.25"
    assert values["change_pct"] == "+1.23%"
