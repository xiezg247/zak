"""P3：共振加权与动量相对强度测试。"""

from __future__ import annotations

from unittest.mock import patch

from vnpy_ashare.quotes.radar.radar_loaders import (
    RadarCardData,
    RadarRow,
    build_radar_resonance_list,
    compute_radar_resonance_scores,
)
from vnpy_ashare.screener.data.market_benchmark import market_benchmark_change_pct, relative_strength_pct
from vnpy_ashare.screener.dimensions.momentum import run_momentum


def _sample_row(vt_symbol: str, *, name: str = "测试") -> RadarRow:
    return RadarRow(
        vt_symbol=vt_symbol,
        name=name,
        symbol=vt_symbol.split(".")[0],
        price=10.0,
        change_pct=1.5,
        metric_label="涨幅",
        metric_value="+1.50%",
        sub_label="换手",
        sub_value="2.00%",
    )


def test_weighted_resonance_prefers_discovery_cards() -> None:
    from vnpy_ashare.quotes.radar.radar_resonance_prefs import save_radar_resonance_weights

    save_radar_resonance_weights(
        {
            "discovery_volume_surge": 2.0,
            "screen_latest": 1.0,
            "screen_task": 1.0,
        }
    )
    payload = {
        "screen_latest": RadarCardData(
            card_id="screen_latest",
            title="选股",
            subtitle="",
            rows=(_sample_row("600000.SSE"),),
            empty_message="",
            updated_at="",
        ),
        "discovery_volume_surge": RadarCardData(
            card_id="discovery_volume_surge",
            title="发现·放量",
            subtitle="",
            rows=(_sample_row("000001.SZSE", name="平安"),),
            empty_message="",
            updated_at="",
        ),
        "b": RadarCardData(
            card_id="screen_task",
            title="选股任务",
            subtitle="",
            rows=(_sample_row("600000.SSE", name="浦发"), _sample_row("000001.SZSE", name="平安")),
            empty_message="",
            updated_at="",
        ),
    }
    scores = compute_radar_resonance_scores(payload)
    assert scores["600000.SSE"] == 2.0
    assert scores["000001.SZSE"] == 3.0

    entries = build_radar_resonance_list(payload)
    assert entries[0].vt_symbol == "000001.SZSE"
    assert entries[0].resonance_score == 3.0


def test_market_benchmark_fallback_to_mean() -> None:
    with patch(
        "vnpy_ashare.screener.data.market_benchmark.fetch_index_ticker",
        side_effect=RuntimeError("offline"),
    ):
        benchmark = market_benchmark_change_pct(
            [{"change_pct": 1.0}, {"change_pct": 3.0}, {"change_pct": 5.0}],
        )
    assert benchmark == 3.0
    assert relative_strength_pct({"change_pct": 5.0}, benchmark) == 2.0


def test_momentum_uses_industry_relative_strength() -> None:
    snapshot = type(
        "Snap",
        (),
        {
            "rows": [
                {
                    "vt_symbol": "600000.SSE",
                    "symbol": "600000",
                    "change_pct": 5.0,
                    "amount": 50_000_000,
                    "total_mv": 600_000,
                },
                {
                    "vt_symbol": "000001.SZSE",
                    "symbol": "000001",
                    "change_pct": 4.0,
                    "amount": 50_000_000,
                    "total_mv": 600_000,
                },
            ],
            "total": 2,
        },
    )()

    with (
        patch(
            "vnpy_ashare.screener.dimensions.momentum.load_screening_quote_snapshot",
            return_value=snapshot,
        ),
        patch(
            "vnpy_ashare.screener.dimensions.momentum.get_stock_industry_map",
            return_value={"600000.SH": "银行", "000001.SZ": "银行"},
        ),
        patch(
            "vnpy_ashare.screener.dimensions.momentum.market_benchmark_change_pct",
            return_value=1.0,
        ),
        patch(
            "vnpy_ashare.screener.dimensions.momentum.attach_industry",
            side_effect=lambda rows, industry_map=None: [{**row, "industry": "银行"} for row in rows],
        ),
        patch(
            "vnpy_ashare.screener.dimensions.momentum.industry_avg_change_map",
            return_value={"银行": 3.0},
        ),
    ):
        hits, scanned = run_momentum(2, weight=0.3)

    assert scanned == 2
    assert hits[0].vt_symbol == "600000.SSE"
    assert hits[0].row["relative_strength"] == 2.0
    assert hits[0].row["strength_basis"] == "行业银行"
    assert hits[0].row["market_relative_strength"] == 4.0
    assert "相对大盘" in hits[0].reason


def test_momentum_uses_relative_strength() -> None:
    snapshot = type(
        "Snap",
        (),
        {
            "rows": [
                {
                    "vt_symbol": "600000.SSE",
                    "symbol": "600000",
                    "change_pct": 5.0,
                    "amount": 50_000_000,
                    "total_mv": 600_000,
                },
                {
                    "vt_symbol": "000001.SZSE",
                    "symbol": "000001",
                    "change_pct": 8.0,
                    "amount": 50_000_000,
                    "total_mv": 600_000,
                },
            ],
            "total": 2,
        },
    )()

    with (
        patch(
            "vnpy_ashare.screener.dimensions.momentum.load_screening_quote_snapshot",
            return_value=snapshot,
        ),
        patch(
            "vnpy_ashare.screener.dimensions.momentum.get_stock_industry_map",
            return_value={},
        ),
        patch(
            "vnpy_ashare.screener.dimensions.momentum.attach_industry",
            side_effect=lambda rows, industry_map=None: list(rows),
        ),
        patch(
            "vnpy_ashare.screener.dimensions.momentum.market_benchmark_change_pct",
            return_value=2.0,
        ),
        patch(
            "vnpy_ashare.screener.dimensions.momentum.industry_avg_change_map",
            return_value={},
        ),
    ):
        hits, scanned = run_momentum(2, weight=0.3)

    assert scanned == 2
    assert hits[0].vt_symbol == "000001.SZSE"
    assert hits[0].row["relative_strength"] == 6.0
    assert "相对大盘" in hits[0].reason
