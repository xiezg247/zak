"""雷达展望全市场扫描测试。"""

from unittest.mock import patch

from vnpy_ashare.quotes.radar.radar_horizon_scan import (
    HorizonScanStats,
    horizon_empty_message,
    local_daily_k_insufficient,
    prefilter_horizon_universe,
)


def test_local_daily_k_insufficient_requires_empty_refined() -> None:
    stats = HorizonScanStats(
        scanned_total=5000,
        excluded_count=3,
        prefilter_total=100,
        refined_total=0,
        kline_missing=60,
    )
    assert local_daily_k_insufficient(stats)

    stats_with_refined = HorizonScanStats(
        scanned_total=5000,
        excluded_count=3,
        prefilter_total=100,
        refined_total=10,
        kline_missing=90,
    )
    assert not local_daily_k_insufficient(stats_with_refined)


def test_horizon_empty_message_no_local_k() -> None:
    stats = HorizonScanStats(scanned_total=100, excluded_count=0, prefilter_total=0, refined_total=0, kline_missing=0)
    with patch(
        "vnpy_ashare.quotes.radar.radar_horizon_scan.collect_daily_k_ready_vt_symbols",
        return_value=set(),
    ):
        message = horizon_empty_message(stats, card_title="未来·关注")
    assert "本地暂无日 K" in message


def test_collect_daily_k_ready_vt_symbols_uses_ttl_cache(monkeypatch) -> None:
    from vnpy_ashare.quotes.radar.radar_horizon_scan import (
        clear_daily_k_ready_cache,
        collect_daily_k_ready_vt_symbols,
    )

    clear_daily_k_ready_cache()
    calls = {"count": 0}

    def _fake_overviews(*, scope: str):
        calls["count"] += 1
        assert scope == "daily"
        from types import SimpleNamespace

        yield SimpleNamespace(symbol="600000", exchange="SSE", count=30)

    monkeypatch.setattr(
        "vnpy_ashare.quotes.radar.radar_horizon_scan.iter_bar_overviews",
        _fake_overviews,
    )
    monkeypatch.setattr(
        "vnpy_ashare.quotes.radar.radar_horizon_scan.horizon_min_signal_bars",
        lambda _config=None: 25,
    )

    first = collect_daily_k_ready_vt_symbols()
    second = collect_daily_k_ready_vt_symbols()
    assert first == {"600000.SSE"}
    assert second == first
    assert calls["count"] == 1
    clear_daily_k_ready_cache()


def test_horizon_empty_message_no_match() -> None:
    stats = HorizonScanStats(
        scanned_total=5000,
        excluded_count=0,
        prefilter_total=80,
        refined_total=40,
        kline_missing=0,
    )
    with patch(
        "vnpy_ashare.quotes.radar.radar_horizon_scan.collect_daily_k_ready_vt_symbols",
        return_value={"600000.SSE"},
    ):
        message = horizon_empty_message(stats, card_title="未来·关注")
    assert "无符合" in message


def test_prefilter_skips_symbols_without_local_daily_k() -> None:
    quote_rows = [
        {"vt_symbol": "600000.SSE", "amount": 1e9, "turnover_rate": 2.0},
        {"vt_symbol": "000001.SZSE", "amount": 2e9, "turnover_rate": 3.0},
    ]
    snapshot = type("Snap", (), {"rows": quote_rows, "total": len(quote_rows)})()

    with patch(
        "vnpy_ashare.quotes.radar.radar_horizon_scan.load_screening_quote_snapshot",
        return_value=snapshot,
    ):
        with patch(
            "vnpy_ashare.quotes.radar.radar_horizon_scan.apply_screening_filters",
            side_effect=lambda rows: rows,
        ):
            with patch(
                "vnpy_ashare.quotes.radar.radar_horizon_scan.collect_daily_k_ready_vt_symbols",
                return_value={"600000.SSE"},
            ):
                prefilter, stats = prefilter_horizon_universe(set(), max_items=10)

    assert prefilter == ["600000.SSE"]
    assert stats.prefilter_total == 1


def test_outlook_judgment_subline_prefers_scenario() -> None:
    from vnpy_ashare.domain.trading.signal_snapshot import SignalSnapshot
    from vnpy_ashare.quotes.radar.radar_horizon_rules import outlook_judgment_subline

    snapshot = SignalSnapshot(
        vt_symbol="600000.SSE",
        strategy_id="Test",
        as_of="2025-01-02",
        signal="buy",
        signal_label="买入",
        signal_date="2025-01-02",
        ref_buy_price=10.0,
        ref_sell_price=None,
        strength=72.0,
        reason_summary="均线多头",
        reasons=("快线在慢线上方",),
        warnings=(),
        last_close=10.5,
    )
    label, value = outlook_judgment_subline(snapshot, scenario_hint="偏多")
    assert label == "5日情景"
    assert value == "偏多"

    label, value = outlook_judgment_subline(snapshot)
    assert label == "距买点"
    assert value == "+5.0%"
