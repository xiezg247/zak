"""雷达卡片数据加载测试。"""

from vnpy_ashare.quotes.radar_catalog import RADAR_CARD_BY_ID
from vnpy_ashare.quotes.radar_loaders import (
    RadarCardData,
    RadarRow,
    _liquidity_metric,
    _merge_row_quotes,
    build_radar_ai_prompt,
    build_radar_resonance_ai_prompt,
    build_radar_resonance_list,
    compute_radar_resonance,
    load_discovery_moneyflow_intraday,
    load_discovery_volume_surge,
    load_screen_latest,
)


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


def test_load_screen_latest_empty(monkeypatch) -> None:
    monkeypatch.setattr("vnpy_ashare.quotes.radar_loaders.get_latest_run", lambda: None)
    spec = RADAR_CARD_BY_ID["screen_latest"]
    data = load_screen_latest(spec)
    assert data.rows == ()
    assert "暂无选股记录" in data.empty_message


def test_load_discovery_moneyflow_intraday_empty(monkeypatch) -> None:
    monkeypatch.setattr(
        "vnpy_ashare.quotes.radar_loaders.run_moneyflow_intraday",
        lambda _n, weight=1.0: ([], 0),
    )
    spec = RADAR_CARD_BY_ID["discovery_moneyflow_intraday"]
    data = load_discovery_moneyflow_intraday(spec)
    assert data.rows == ()
    assert "暂无行情数据" in data.empty_message


def test_compute_radar_resonance() -> None:
    payload = {
        "a": RadarCardData("a", "卡A", "", (_sample_row("600000.SSE"),), "", ""),
        "b": RadarCardData("b", "卡B", "", (_sample_row("600000.SSE"), _sample_row("000001.SZSE")), "", ""),
    }
    resonance = compute_radar_resonance(payload)
    assert resonance == {"600000.SSE": 2}


def test_build_radar_ai_prompt_includes_resonance() -> None:
    payload = {
        "a": RadarCardData("a", "选股", "共 1 只", (_sample_row("600000.SSE", name="浦发"),), "", "2025-01-01"),
        "b": RadarCardData("b", "发现", "", (_sample_row("600000.SSE", name="浦发"),), "", ""),
    }
    prompt = build_radar_ai_prompt(payload)
    assert "共振标的" in prompt
    assert "浦发" in prompt
    assert "不要编造" in prompt


def test_build_radar_resonance_list() -> None:
    payload = {
        "a": RadarCardData("a", "选股", "", (_sample_row("600000.SSE", name="浦发"),), "", ""),
        "b": RadarCardData(
            "b",
            "发现",
            "",
            (_sample_row("600000.SSE", name="浦发"), _sample_row("000001.SZSE", name="平安")),
            "",
            "",
        ),
    }
    entries = build_radar_resonance_list(payload)
    assert len(entries) == 1
    assert entries[0].vt_symbol == "600000.SSE"
    assert entries[0].card_count == 2
    assert entries[0].card_titles == ("选股", "发现")


def test_build_radar_resonance_ai_prompt() -> None:
    payload = {
        "a": RadarCardData("a", "选股", "", (_sample_row("600000.SSE", name="浦发"),), "", ""),
        "b": RadarCardData("b", "发现", "", (_sample_row("600000.SSE", name="浦发"),), "", ""),
    }
    prompt = build_radar_resonance_ai_prompt(payload)
    assert "共振标的" in prompt
    assert "浦发" in prompt


def test_liquidity_metric_prefers_amount_when_volume_missing() -> None:
    row = {"vt_symbol": "600000.SSE", "volume": 0, "amount": 12_500_000, "change_pct": 2.5}
    label, value, sub_label, sub_value = _liquidity_metric(row)
    assert label == "成交额"
    assert "万" in value
    assert sub_label == "涨幅"


def test_merge_row_quotes_fills_from_cache(monkeypatch) -> None:
    monkeypatch.setattr(
        "vnpy_ashare.quotes.radar_loaders.get_market_quotes_cache",
        lambda: [{"vt_symbol": "600000.SSE", "amount": 99_000_000, "volume": 12345}],
    )
    merged = _merge_row_quotes({"vt_symbol": "600000.SSE", "volume": 0})
    assert merged["amount"] == 99_000_000
    assert merged["volume"] == 12345


def test_load_discovery_moneyflow_fallback(monkeypatch) -> None:
    from vnpy_ashare.quotes.radar_catalog import RADAR_CARD_BY_ID
    from vnpy_ashare.screener.dimensions.base import DimensionHit

    monkeypatch.setattr(
        "vnpy_ashare.quotes.radar_loaders.run_moneyflow_intraday",
        lambda _n, weight=1.0: ([], 100),
    )
    fake_hit = DimensionHit(
        vt_symbol="600000.SSE",
        dimension_id="moneyflow",
        label="资金",
        weight=1.0,
        score=1.0,
        reason="test",
        row={
            "vt_symbol": "600000.SSE",
            "name": "浦发",
            "symbol": "600000",
            "net_mf_amount": 1000,
            "change_pct": 1.0,
        },
    )
    monkeypatch.setattr(
        "vnpy_ashare.quotes.radar_loaders.run_moneyflow",
        lambda _n, weight=1.0: ([fake_hit], 100),
    )
    data = load_discovery_moneyflow_intraday(RADAR_CARD_BY_ID["discovery_moneyflow_intraday"])
    assert len(data.rows) == 1
    assert data.rows[0].metric_label == "主力净流入"


def test_load_discovery_volume_surge_keeps_surge_when_ratio_empty(monkeypatch) -> None:
    from vnpy_ashare.quotes.radar_catalog import RADAR_CARD_BY_ID
    from vnpy_ashare.screener.dimensions.base import DimensionHit

    surge_hit = DimensionHit(
        vt_symbol="600000.SSE",
        dimension_id="volume_surge",
        label="放量",
        weight=1.0,
        score=90.0,
        reason="test",
        row={
            "vt_symbol": "600000.SSE",
            "name": "浦发",
            "symbol": "600000",
            "last_price": 10.0,
            "change_pct": 2.0,
            "volume": 0,
            "amount": 0,
        },
    )
    monkeypatch.setattr(
        "vnpy_ashare.quotes.radar_loaders.run_volume_surge",
        lambda _n, weight=1.0: ([surge_hit], 5512),
    )
    monkeypatch.setattr(
        "vnpy_ashare.quotes.radar_loaders.run_volume_ratio",
        lambda _n, weight=1.0: ([], 5512),
    )
    data = load_discovery_volume_surge(RADAR_CARD_BY_ID["discovery_volume_surge"])
    assert len(data.rows) == 1
    assert data.rows[0].name == "浦发"


def test_load_radar_card_unknown() -> None:
    import pytest

    with pytest.raises(ValueError, match="未知雷达卡片"):
        from vnpy_ashare.quotes.radar_loaders import load_radar_card

        load_radar_card("not_exists")
