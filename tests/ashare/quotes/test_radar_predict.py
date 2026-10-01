"""雷达预测基线与 loader 测试。"""

from __future__ import annotations

from vnpy_ashare.quotes.radar.predict.baseline_ranker import rank_baseline_predict
from vnpy_ashare.quotes.radar.predict.predict_scan import rank_predict_hits, scan_predict
from vnpy_ashare.quotes.radar.radar_catalog import RADAR_CARD_BY_ID
from vnpy_ashare.quotes.radar.radar_horizon_predict import build_predict_ai_prompt, load_outlook_predict
from vnpy_ashare.quotes.radar.radar_models import RadarCardData, RadarRow


def test_rank_baseline_predict_orders_by_composite_score(monkeypatch) -> None:
    monkeypatch.setattr(
        "vnpy_ashare.quotes.radar.predict.baseline_ranker.get_stock_industry_map",
        lambda: {},
    )
    monkeypatch.setattr(
        "vnpy_ashare.quotes.radar.predict.baseline_ranker.attach_industry",
        lambda rows, **kwargs: rows,
    )
    monkeypatch.setattr(
        "vnpy_ashare.quotes.radar.predict.baseline_ranker.market_benchmark_change_pct",
        lambda _rows: 0.5,
    )
    monkeypatch.setattr(
        "vnpy_ashare.quotes.radar.predict.baseline_ranker.industry_avg_change_map",
        lambda _rows: {},
    )

    rows = [
        {"vt_symbol": "600000.SSE", "change_pct": 1.0, "volume_ratio": 1.1, "turnover_rate": 1.0},
        {"vt_symbol": "000001.SZSE", "change_pct": 4.0, "volume_ratio": 2.0, "turnover_rate": 3.0},
        {"vt_symbol": "000002.SZSE", "change_pct": -2.0, "volume_ratio": 0.8, "turnover_rate": 0.5},
    ]
    hits = rank_baseline_predict(rows)
    assert len(hits) == 3
    assert hits[0].vt_symbol == "000001.SZSE"
    assert hits[0].score >= hits[1].score >= hits[2].score
    assert 0.05 <= hits[0].p_up <= 0.95


def test_rank_predict_hits_uses_baseline(monkeypatch) -> None:
    monkeypatch.setattr(
        "vnpy_ashare.quotes.radar.predict.baseline_ranker.get_stock_industry_map",
        lambda: {},
    )
    monkeypatch.setattr(
        "vnpy_ashare.quotes.radar.predict.baseline_ranker.attach_industry",
        lambda rows, **kwargs: rows,
    )
    monkeypatch.setattr(
        "vnpy_ashare.quotes.radar.predict.baseline_ranker.market_benchmark_change_pct",
        lambda _rows: 0.0,
    )
    monkeypatch.setattr(
        "vnpy_ashare.quotes.radar.predict.baseline_ranker.industry_avg_change_map",
        lambda _rows: {},
    )
    rows = [{"vt_symbol": "600000.SSE", "change_pct": 2.0, "volume_ratio": 1.5, "turnover_rate": 1.2}]
    hits, variant, label = rank_predict_hits(rows, top_n=1, mode="auto")
    assert variant == "predict_baseline"
    assert label == "统计基线"
    assert len(hits) == 1
    assert hits[0].score_label == "基准分"


def test_scan_predict_builds_rows(monkeypatch) -> None:
    from vnpy_ashare.domain.radar.horizon import HorizonScanStats

    monkeypatch.setattr(
        "vnpy_ashare.quotes.radar.predict.predict_scan.collect_outlook_exclusion_vt_symbols",
        lambda: set(),
    )
    monkeypatch.setattr(
        "vnpy_ashare.quotes.radar.predict.predict_scan.prefilter_horizon_universe",
        lambda _excluded: (
            ["600000.SSE", "000001.SZSE"],
            HorizonScanStats(
                scanned_total=100,
                excluded_count=0,
                prefilter_total=2,
                refined_total=0,
                kline_missing=0,
            ),
        ),
    )
    monkeypatch.setattr(
        "vnpy_ashare.quotes.radar.predict.predict_scan.load_screening_quote_snapshot",
        lambda: type(
            "Snap",
            (),
            {
                "rows": [
                    {"vt_symbol": "600000.SSE", "name": "浦发", "change_pct": 1.0, "volume_ratio": 1.2, "turnover_rate": 1.0, "last_price": 10.0},
                    {"vt_symbol": "000001.SZSE", "name": "平安", "change_pct": 3.0, "volume_ratio": 1.8, "turnover_rate": 2.0, "last_price": 12.0},
                ],
            },
        )(),
    )
    monkeypatch.setattr(
        "vnpy_ashare.quotes.radar.predict.baseline_ranker.get_stock_industry_map",
        lambda: {},
    )
    monkeypatch.setattr(
        "vnpy_ashare.quotes.radar.predict.baseline_ranker.attach_industry",
        lambda rows, **kwargs: rows,
    )
    monkeypatch.setattr(
        "vnpy_ashare.quotes.radar.predict.baseline_ranker.market_benchmark_change_pct",
        lambda _rows: 0.5,
    )
    monkeypatch.setattr(
        "vnpy_ashare.quotes.radar.predict.baseline_ranker.industry_avg_change_map",
        lambda _rows: {},
    )
    monkeypatch.setattr(
        "vnpy_ashare.quotes.radar.predict.predict_scan.name_map_for_symbols",
        lambda _symbols: {"600000.SSE": "浦发", "000001.SZSE": "平安"},
    )

    result = scan_predict(top_n=2)
    assert len(result.rows) == 2
    assert result.rows[0].metric_label == "看涨概率"
    assert result.rows[0].sub_label == "基准分"


def test_rank_predict_hits_force_baseline(monkeypatch) -> None:
    monkeypatch.setattr(
        "vnpy_ashare.quotes.radar.predict.baseline_ranker.get_stock_industry_map",
        lambda: {},
    )
    monkeypatch.setattr(
        "vnpy_ashare.quotes.radar.predict.baseline_ranker.attach_industry",
        lambda rows, **kwargs: rows,
    )
    monkeypatch.setattr(
        "vnpy_ashare.quotes.radar.predict.baseline_ranker.market_benchmark_change_pct",
        lambda _rows: 0.0,
    )
    monkeypatch.setattr(
        "vnpy_ashare.quotes.radar.predict.baseline_ranker.industry_avg_change_map",
        lambda _rows: {},
    )
    rows = [{"vt_symbol": "600000.SSE", "change_pct": 2.0, "volume_ratio": 1.5, "turnover_rate": 1.2}]
    hits, variant, label = rank_predict_hits(rows, top_n=1, mode="baseline")
    assert variant == "predict_baseline"
    assert label == "统计基线"


def test_load_outlook_predict_no_cache(monkeypatch) -> None:
    monkeypatch.setattr(
        "vnpy_ashare.quotes.radar.radar_horizon_predict.get_latest_predict_cache",
        lambda: None,
    )
    monkeypatch.setattr(
        "vnpy_ashare.quotes.radar.radar_horizon_predict.collect_daily_k_ready_vt_symbols",
        lambda: {"600000.SSE"},
    )
    spec = RADAR_CARD_BY_ID["outlook_predict"]
    data = load_outlook_predict(spec, force_recompute=False)
    assert "预测" in data.title
    assert not data.rows
    assert "暂无预测快照" in data.empty_message


def test_build_predict_ai_prompt() -> None:
    row = RadarRow(
        vt_symbol="600000.SSE",
        name="浦发",
        symbol="600000",
        price=10.0,
        change_pct=1.5,
        metric_label="看涨概率",
        metric_value="62%",
        sub_label="基准分",
        sub_value="62.0",
    )
    data = RadarCardData(
        card_id="outlook_predict",
        title="未来·预测",
        subtitle="约 5 日 · 统计基线",
        rows=(row,),
        empty_message="",
        updated_at="2025-01-01",
    )
    prompt = build_predict_ai_prompt(data)
    assert "未来·预测" in prompt
    assert "统计基线" in prompt
    assert "非确定性预测" in prompt
    assert "浦发" in prompt
    assert "62%" in prompt
