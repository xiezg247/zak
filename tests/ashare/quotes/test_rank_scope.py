"""榜单自选范围测试。"""

from unittest.mock import MagicMock

from vnpy.trader.constant import Exchange

from vnpy_ashare.domain.market.quote_snapshot import QuoteSnapshot
from vnpy_ashare.quotes.rank.rank_catalog import get_rank_definition
from vnpy_ashare.quotes.rank.rank_scope import load_market_rank_catalog, load_watchlist_rank_catalog


def _quote(
    change_pct: float,
    *,
    speed: float = 0.0,
    volume_ratio: float = 0.0,
    net_mf_amount: float = 0.0,
) -> QuoteSnapshot:
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
        volume_ratio=volume_ratio,
        net_mf_amount=net_mf_amount,
    )


def test_load_watchlist_rank_catalog_sorts_by_change_pct(monkeypatch) -> None:
    monkeypatch.setattr(
        "vnpy_ashare.quotes.rank.rank_scope.load_watchlist_rows",
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
    monkeypatch.setattr("vnpy_ashare.quotes.rank.rank_scope.load_watchlist_rows", lambda: [])
    store = MagicMock()
    spec = get_rank_definition("watchlist_change_pct")
    tf_symbols, quotes = load_watchlist_rank_catalog(store, spec)
    assert tf_symbols == []
    assert quotes == {}
    store.get_quotes.assert_not_called()


def test_load_market_rank_catalog_uses_change_pct_pool_when_volume_ratio_zset_empty() -> None:
    store = MagicMock()
    store.list_all_rank_symbols.side_effect = lambda *, field, ascending: [] if field == "volume_ratio" else ["000001.SZ", "600000.SH"]
    store.get_quotes.return_value = {
        "600000.SH": _quote(1.0, volume_ratio=2.5),
        "000001.SZ": _quote(3.0, volume_ratio=1.2),
    }
    spec = get_rank_definition("volume_ratio")
    tf_symbols, quotes = load_market_rank_catalog(store, spec)
    assert tf_symbols == ["600000.SH", "000001.SZ"]
    assert len(quotes) == 2
    store.get_quotes.assert_called_once_with(["000001.SZ", "600000.SH"])


def test_load_market_rank_catalog_prefers_redis_zset() -> None:
    store = MagicMock()
    store.list_all_rank_symbols.return_value = ["600000.SH", "000001.SZ"]
    store.get_quotes.return_value = {
        "600000.SH": _quote(1.0, volume_ratio=2.5),
        "000001.SZ": _quote(3.0, volume_ratio=1.2),
    }
    spec = get_rank_definition("volume_ratio")
    tf_symbols, _quotes = load_market_rank_catalog(store, spec)
    assert tf_symbols == ["600000.SH", "000001.SZ"]


def test_load_market_rank_catalog_falls_back_when_finalize_filters_all() -> None:
    store = MagicMock()
    store.list_all_rank_symbols.side_effect = lambda *, field, ascending: ["600000.SH"] if field == "volume_ratio" else ["000001.SZ", "600000.SH"]

    def _get_quotes(tf_symbols: list[str]) -> dict[str, QuoteSnapshot]:
        if tf_symbols == ["600000.SH"]:
            return {"600000.SH": _quote(1.0, volume_ratio=0.0)}
        return {
            "600000.SH": _quote(1.0, volume_ratio=2.5),
            "000001.SZ": _quote(3.0, volume_ratio=1.2),
        }

    store.get_quotes.side_effect = _get_quotes
    spec = get_rank_definition("volume_ratio")
    tf_symbols, quotes = load_market_rank_catalog(store, spec)
    assert tf_symbols == ["600000.SH", "000001.SZ"]
    assert len(quotes) == 2
