"""榜单自选范围测试。"""

from unittest.mock import MagicMock

from vnpy.trader.constant import Exchange

from vnpy_ashare.quotes.rank_catalog import get_rank_definition
from vnpy_ashare.quotes.rank_scope import load_watchlist_rank_catalog
from vnpy_ashare.quotes.snapshot import QuoteSnapshot


def _quote(change_pct: float, *, speed: float = 0.0) -> QuoteSnapshot:
    return QuoteSnapshot(
        symbol="600000.SH",
        name="浦发",
        last_price=10.0,
        prev_close=9.0,
        open_price=9.5,
        high_price=10.0,
        low_price=9.5,
        change_amount=1.0,
        change_pct=change_pct,
        turnover_rate=1.0,
        volume=1000.0,
        change_speed_5m=speed,
    )


def test_load_watchlist_rank_catalog_sorts_by_change_pct(monkeypatch) -> None:
    monkeypatch.setattr(
        "vnpy_ashare.quotes.rank_scope.load_watchlist_rows",
        lambda: [("600000", Exchange.SSE, "浦发"), ("000001", Exchange.SZSE, "平安")],
    )
    store = MagicMock()
    store.get_quotes.return_value = {
        "600000.SH": _quote(1.0),
        "000001.SZ": _quote(3.0),
    }
    spec = get_rank_definition("watchlist_change_pct")
    tf_symbols, quotes = load_watchlist_rank_catalog(store, spec)
    assert tf_symbols == ["000001.SZ", "600000.SH"]
    assert len(quotes) == 2


def test_load_watchlist_rank_catalog_empty_pool(monkeypatch) -> None:
    monkeypatch.setattr("vnpy_ashare.quotes.rank_scope.load_watchlist_rows", lambda: [])
    store = MagicMock()
    spec = get_rank_definition("watchlist_change_pct")
    tf_symbols, quotes = load_watchlist_rank_catalog(store, spec)
    assert tf_symbols == []
    assert quotes == {}
    store.get_quotes.assert_not_called()
