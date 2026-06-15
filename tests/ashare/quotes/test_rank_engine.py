"""榜单过滤与排序逻辑测试。"""

import pytest

from vnpy_ashare.quotes.market.market_breadth import LIMIT_DOWN_PCT, LIMIT_UP_PCT
from vnpy_ashare.quotes.rank.rank_catalog import NEAR_LIMIT_UP_MIN, get_rank_definition
from vnpy_ashare.quotes.rank.rank_engine import (
    apply_rank_catalog,
    compute_intraday_change_pct,
    quote_matches_rank,
)
from vnpy_ashare.quotes.core.snapshot import QuoteSnapshot


def _quote(
    *,
    change_pct: float = 0.0,
    prev_close: float = 10.0,
    open_price: float = 10.0,
    last_price: float = 10.0,
    volume_ratio: float = 0.0,
    net_mf_amount: float = 0.0,
    change_speed_5m: float = 0.0,
    limit_times: float = 0.0,
) -> QuoteSnapshot:
    return QuoteSnapshot(
        symbol="600000.SH",
        name="测试",
        last_price=last_price,
        prev_close=prev_close,
        open_price=open_price,
        high_price=max(last_price, open_price),
        low_price=min(last_price, open_price),
        change_amount=last_price - prev_close,
        change_pct=change_pct,
        turnover_rate=1.0,
        volume=1000.0,
        amount=10000.0,
        amplitude=1.0,
        volume_ratio=volume_ratio,
        net_mf_amount=net_mf_amount,
        change_speed_5m=change_speed_5m,
        limit_times=limit_times,
    )


def test_compute_intraday_change_pct() -> None:
    quote = _quote(prev_close=10.0, open_price=9.5, last_price=10.2)
    assert compute_intraday_change_pct(quote) == pytest.approx(7.0)


def test_limit_up_filter() -> None:
    spec = get_rank_definition("limit_up")
    assert quote_matches_rank(_quote(change_pct=LIMIT_UP_PCT), spec)
    assert not quote_matches_rank(_quote(change_pct=LIMIT_UP_PCT - 0.1), spec)


def test_near_limit_up_filter() -> None:
    spec = get_rank_definition("near_limit_up")
    assert quote_matches_rank(_quote(change_pct=NEAR_LIMIT_UP_MIN), spec)
    assert quote_matches_rank(_quote(change_pct=LIMIT_UP_PCT - 0.1), spec)
    assert not quote_matches_rank(_quote(change_pct=LIMIT_UP_PCT), spec)
    assert not quote_matches_rank(_quote(change_pct=NEAR_LIMIT_UP_MIN - 0.1), spec)


def test_limit_down_filter() -> None:
    spec = get_rank_definition("limit_down")
    assert quote_matches_rank(_quote(change_pct=LIMIT_DOWN_PCT), spec)
    assert not quote_matches_rank(_quote(change_pct=LIMIT_DOWN_PCT + 0.1), spec)


def test_gap_up_rally_filter() -> None:
    spec = get_rank_definition("gap_up_rally")
    matched = _quote(prev_close=10.0, open_price=9.8, last_price=10.1, change_pct=1.0)
    assert quote_matches_rank(matched, spec)
    assert not quote_matches_rank(_quote(prev_close=10.0, open_price=10.1, last_price=10.2), spec)
    assert not quote_matches_rank(_quote(prev_close=10.0, open_price=9.8, last_price=9.7), spec)


def test_gap_down_fade_filter() -> None:
    spec = get_rank_definition("gap_down_fade")
    matched = _quote(prev_close=10.0, open_price=10.2, last_price=9.9, change_pct=-1.0)
    assert quote_matches_rank(matched, spec)
    assert not quote_matches_rank(_quote(prev_close=10.0, open_price=9.8, last_price=9.7), spec)


def test_net_mf_rank_filters() -> None:
    in_spec = get_rank_definition("net_mf_in")
    out_spec = get_rank_definition("net_mf_out")
    assert quote_matches_rank(_quote(net_mf_amount=100.0), in_spec)
    assert not quote_matches_rank(_quote(net_mf_amount=-1.0), in_spec)
    assert quote_matches_rank(_quote(net_mf_amount=-100.0), out_spec)
    assert not quote_matches_rank(_quote(net_mf_amount=1.0), out_spec)


def test_volume_ratio_rank_filter() -> None:
    spec = get_rank_definition("volume_ratio")
    assert quote_matches_rank(_quote(volume_ratio=1.2), spec)
    assert not quote_matches_rank(_quote(volume_ratio=0.0), spec)


def test_limit_times_rank_filter() -> None:
    spec = get_rank_definition("limit_times")
    assert quote_matches_rank(_quote(limit_times=2.0), spec)
    assert quote_matches_rank(_quote(limit_times=1.0), spec)
    assert not quote_matches_rank(_quote(limit_times=0.0), spec)


def test_change_speed_5m_rank_filter() -> None:
    spec = get_rank_definition("change_speed_5m")
    assert quote_matches_rank(_quote(change_speed_5m=0.5), spec)
    assert not quote_matches_rank(_quote(change_speed_5m=0.0), spec)


def test_apply_rank_catalog_orders_near_limit_up() -> None:
    spec = get_rank_definition("near_limit_up")
    quotes = {
        "A": _quote(change_pct=8.0),
        "B": _quote(change_pct=7.5),
        "C": _quote(change_pct=10.0),
        "D": _quote(change_pct=5.0),
    }
    result = apply_rank_catalog(list(quotes), quotes, spec)
    assert result == ["A", "B"]
