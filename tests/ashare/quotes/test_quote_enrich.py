"""行情 Tushare 因子合并测试。"""

from unittest.mock import patch

from vnpy_ashare.quotes.enrich import enrich_quotes_with_tushare_factors, load_tushare_factor_maps_by_tickflow
from vnpy_ashare.quotes.snapshot import QuoteSnapshot


def _quote(tf_symbol: str = "600000.SH") -> QuoteSnapshot:
    return QuoteSnapshot(
        symbol=tf_symbol,
        name="测试",
        last_price=10.0,
        prev_close=9.8,
        open_price=9.9,
        high_price=10.1,
        low_price=9.8,
        change_amount=0.2,
        change_pct=2.0,
        turnover_rate=1.0,
        volume=1000.0,
    )


def test_load_tushare_factor_maps_by_tickflow() -> None:
    basic_rows = [
        {"vt_symbol": "600000.SSE", "volume_ratio": 1.5},
        {"vt_symbol": "000001.SZSE", "volume_ratio": 0.0},
    ]
    mf_rows = [
        {"vt_symbol": "600000.SSE", "net_mf_amount": 1234.0},
        {"vt_symbol": "000001.SZSE", "net_mf_amount": -500.0},
    ]
    with (
        patch("vnpy_ashare.quotes.enrich.fetch_daily_basic_with_fallback", return_value=(basic_rows, "20260613")),
        patch("vnpy_ashare.quotes.enrich.fetch_moneyflow_with_fallback", return_value=(mf_rows, "20260613")),
    ):
        ratio_map, mf_map = load_tushare_factor_maps_by_tickflow()

    assert ratio_map == {"600000.SH": 1.5}
    assert mf_map == {"600000.SH": 1234.0, "000001.SZ": -500.0}


def test_load_limit_times_map_by_tickflow() -> None:
    from vnpy_ashare.quotes.enrich import load_limit_times_map_by_tickflow

    rows = [
        {"ts_code": "600000.SH", "limit": "U", "limit_times": 3},
        {"ts_code": "000001.SZ", "limit": "U", "limit_times": 1},
        {"ts_code": "300001.SZ", "limit": "D", "limit_times": 2},
    ]
    with patch("vnpy_ashare.quotes.enrich.fetch_limit_list_with_fallback", return_value=(rows, "20260613")):
        result = load_limit_times_map_by_tickflow()
    assert result == {"600000.SH": 3.0, "000001.SZ": 1.0}


def test_enrich_quotes_with_tushare_factors() -> None:
    quotes = {"600000.SH": _quote(), "000001.SZ": _quote("000001.SZ")}
    with (
        patch(
            "vnpy_ashare.quotes.enrich.load_tushare_factor_maps_by_tickflow",
            return_value=({"600000.SH": 2.1}, {"600000.SH": 888.0, "000001.SZ": -100.0}),
        ),
        patch(
            "vnpy_ashare.quotes.enrich.load_limit_times_map_by_tickflow",
            return_value={"600000.SH": 2.0},
        ),
    ):
        enrich_quotes_with_tushare_factors(quotes)

    assert quotes["600000.SH"].volume_ratio == 2.1
    assert quotes["600000.SH"].net_mf_amount == 888.0
    assert quotes["600000.SH"].limit_times == 2.0
    assert quotes["000001.SZ"].volume_ratio == 0.0
    assert quotes["000001.SZ"].net_mf_amount == -100.0


def test_enrich_limit_up_fallback_to_one_board() -> None:
    from vnpy_ashare.quotes.market_breadth import LIMIT_UP_PCT

    quote = _quote()
    quote.change_pct = LIMIT_UP_PCT
    quotes = {"600000.SH": quote}
    with (
        patch("vnpy_ashare.quotes.enrich.load_tushare_factor_maps_by_tickflow", return_value=({}, {})),
        patch("vnpy_ashare.quotes.enrich.load_limit_times_map_by_tickflow", return_value={}),
    ):
        enrich_quotes_with_tushare_factors(quotes)
    assert quotes["600000.SH"].limit_times == 1.0


def test_enrich_quotes_tushare_failure_is_noop() -> None:
    quotes = {"600000.SH": _quote()}
    with (
        patch("vnpy_ashare.quotes.enrich.load_tushare_factor_maps_by_tickflow", side_effect=RuntimeError("offline")),
        patch("vnpy_ashare.quotes.enrich.load_limit_times_map_by_tickflow", side_effect=RuntimeError("offline")),
    ):
        enrich_quotes_with_tushare_factors(quotes)
    assert quotes["600000.SH"].volume_ratio == 0.0
    assert quotes["600000.SH"].net_mf_amount == 0.0
    assert quotes["600000.SH"].limit_times == 0.0


def test_fill_missing_tushare_factors() -> None:
    from vnpy_ashare.quotes.enrich import fill_missing_tushare_factors

    quotes = {"600000.SH": _quote(), "000001.SZ": _quote("000001.SZ")}
    quotes["600000.SH"].volume_ratio = 1.1
    with patch(
        "vnpy_ashare.quotes.enrich.get_cached_tushare_factor_maps",
        return_value=({"600000.SH": 2.0, "000001.SZ": 1.5}, {"000001.SZ": -200.0}),
    ):
        fill_missing_tushare_factors(quotes)

    assert quotes["600000.SH"].volume_ratio == 1.1
    assert quotes["000001.SZ"].volume_ratio == 1.5
    assert quotes["000001.SZ"].net_mf_amount == -200.0


def test_fill_missing_limit_times_fallback_to_one_board() -> None:
    from vnpy_ashare.quotes.enrich import fill_missing_tushare_factors
    from vnpy_ashare.quotes.market_breadth import LIMIT_UP_PCT

    quote = _quote()
    quote.change_pct = LIMIT_UP_PCT
    quotes = {"600000.SH": quote}
    with (
        patch(
            "vnpy_ashare.quotes.enrich.get_cached_tushare_factor_maps",
            return_value=({}, {}),
        ),
        patch(
            "vnpy_ashare.quotes.enrich.get_cached_limit_times_map",
            return_value={},
        ),
    ):
        fill_missing_tushare_factors(quotes)
    assert quotes["600000.SH"].limit_times == 1.0
