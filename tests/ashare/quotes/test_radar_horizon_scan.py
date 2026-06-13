"""雷达展望全市场扫描测试。"""

from unittest.mock import patch

from vnpy_ashare.quotes.radar_horizon_scan import (
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
        "vnpy_ashare.quotes.radar_horizon_scan.collect_daily_k_ready_vt_symbols",
        return_value=set(),
    ):
        message = horizon_empty_message(stats, card_title="未来·关注")
    assert "本地暂无日 K" in message


def test_horizon_empty_message_no_match() -> None:
    stats = HorizonScanStats(
        scanned_total=5000,
        excluded_count=0,
        prefilter_total=80,
        refined_total=40,
        kline_missing=0,
    )
    with patch(
        "vnpy_ashare.quotes.radar_horizon_scan.collect_daily_k_ready_vt_symbols",
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
        "vnpy_ashare.quotes.radar_horizon_scan.load_screening_quote_snapshot",
        return_value=snapshot,
    ):
        with patch(
            "vnpy_ashare.quotes.radar_horizon_scan.apply_screening_filters",
            side_effect=lambda rows: rows,
        ):
            with patch(
                "vnpy_ashare.quotes.radar_horizon_scan.collect_daily_k_ready_vt_symbols",
                return_value={"600000.SSE"},
            ):
                prefilter, stats = prefilter_horizon_universe(set(), max_items=10)

    assert prefilter == ["600000.SSE"]
    assert stats.prefilter_total == 1
