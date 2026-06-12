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
        "vnpy_ashare.quotes.radar_models.get_market_quotes_cache",
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


def test_load_watchlist_intraday_empty_pool(monkeypatch) -> None:
    from vnpy_ashare.quotes.radar_watchlist import load_watchlist_intraday

    monkeypatch.setattr(
        "vnpy_ashare.quotes.radar_watchlist.collect_personal_vt_symbols",
        lambda max_items=50: [],
    )
    spec = RADAR_CARD_BY_ID["watchlist_intraday"]
    data = load_watchlist_intraday(spec)
    assert data.rows == ()
    assert "自选池为空" in data.empty_message


def test_watchlist_moneyflow_metric() -> None:
    from vnpy_ashare.quotes.radar_moneyflow import watchlist_moneyflow_metric

    label, value, sub_label, sub_value = watchlist_moneyflow_metric(
        {"vt_symbol": "600000.SSE", "net_mf_amount": 12345, "change_pct": 1.2}
    )
    assert label == "主力净流入"
    assert "12,345" in value
    assert sub_label == "涨幅"


def test_load_watchlist_intraday_fallback_rank(monkeypatch) -> None:
    from vnpy_ashare.quotes.radar_watchlist import load_watchlist_intraday

    monkeypatch.setattr(
        "vnpy_ashare.quotes.radar_watchlist.collect_personal_vt_symbols",
        lambda max_items=50: ["600000.SSE", "000001.SZSE"],
    )
    monkeypatch.setattr(
        "vnpy_ashare.quotes.radar_watchlist.compute_signal_transitions",
        lambda *args, **kwargs: {},
    )
    monkeypatch.setattr(
        "vnpy_ashare.quotes.radar_watchlist._quotes_for_candidates",
        lambda _candidates: {
            "600000.SSE": {
                "vt_symbol": "600000.SSE",
                "symbol": "600000",
                "name": "浦发",
                "last_price": 10.0,
                "change_pct": 0.3,
            },
            "000001.SZSE": {
                "vt_symbol": "000001.SZSE",
                "symbol": "000001",
                "name": "平安",
                "last_price": 11.0,
                "change_pct": -0.5,
            },
        },
    )
    monkeypatch.setattr(
        "vnpy_ashare.quotes.radar_watchlist.enrich_quotes_with_moneyflow",
        lambda quotes_by_vt, **kwargs: quotes_by_vt,
    )
    spec = RADAR_CARD_BY_ID["watchlist_intraday"]
    data = load_watchlist_intraday(spec)
    assert len(data.rows) == 2
    assert "涨跌幅前列" in data.subtitle


def test_load_sector_theme_empty(monkeypatch) -> None:
    from vnpy_ashare.quotes.radar_sector import load_sector_theme

    monkeypatch.setattr(
        "vnpy_ashare.quotes.radar_sector.run_sector_strength",
        lambda _n, weight=1.0: ([], 0),
    )
    spec = RADAR_CARD_BY_ID["sector_theme"]
    data = load_sector_theme(spec)
    assert data.rows == ()
    assert "板块主线" in data.empty_message


def test_load_outlook_horizon_no_candidates(monkeypatch) -> None:
    from vnpy_ashare.quotes.radar_horizon import load_outlook_horizon

    monkeypatch.setattr(
        "vnpy_ashare.quotes.radar_horizon.collect_horizon_candidates",
        lambda max_items=40: [],
    )
    spec = RADAR_CARD_BY_ID["outlook_horizon"]
    data = load_outlook_horizon(spec)
    assert data.rows == ()
    assert "暂无候选" in data.empty_message


def test_build_outlook_ai_prompt() -> None:
    from vnpy_ashare.quotes.radar_horizon import build_outlook_ai_prompt

    payload = {
        "outlook_horizon": RadarCardData(
            "outlook_horizon",
            "未来·展望",
            "未来关注 · 约 5 日窗口",
            (_sample_row("600000.SSE", name="浦发"),),
            "",
            "",
        ),
    }
    prompt = build_outlook_ai_prompt(payload, variant="watch_next")
    assert "非涨跌预测" in prompt
    assert "浦发" in prompt


def test_build_radar_card_ai_prompt_watchlist() -> None:
    from vnpy_ashare.quotes.radar_loaders import build_radar_card_ai_prompt

    data = RadarCardData(
        "watchlist_intraday",
        "自选·异动",
        "自选异动 Top 1",
        (_sample_row("600000.SSE", name="浦发"),),
        "",
        "",
        ai_hint="信号跃迁 1 只：观望→买入",
    )
    prompt = build_radar_card_ai_prompt("watchlist_intraday", data)
    assert "自选·异动" in prompt
    assert "信号跃迁" in prompt
    assert "浦发" in prompt


def test_transition_label() -> None:
    from vnpy_ashare.domain.signal_snapshot import SignalSnapshot
    from vnpy_ashare.quotes.radar_signals import transition_label

    before = SignalSnapshot(
        vt_symbol="600000.SSE",
        strategy_id="AshareDoubleMaStrategy",
        as_of="2025-01-01",
        signal="hold",
        signal_label="观望",
        signal_date=None,
        ref_buy_price=None,
        ref_sell_price=None,
        strength=50.0,
        reason_summary="",
        reasons=(),
        warnings=(),
    )
    after = SignalSnapshot(
        vt_symbol="600000.SSE",
        strategy_id="AshareDoubleMaStrategy",
        as_of="2025-01-02",
        signal="buy",
        signal_label="买入",
        signal_date="2025-01-02",
        ref_buy_price=10.0,
        ref_sell_price=None,
        strength=72.0,
        reason_summary="",
        reasons=(),
        warnings=(),
    )
    assert transition_label(before, after) == "观望→买入"
    assert transition_label(after, after) is None


def test_build_outlook_digest() -> None:
    from vnpy_ashare.quotes.radar_horizon import build_outlook_digest

    rows = (
        RadarRow(
            "600000.SSE",
            "浦发",
            "600000",
            10.0,
            1.0,
            "买入",
            "72",
            "事件",
            "—",
        ),
    )
    digest = build_outlook_digest(rows, variant="watch_next")
    assert "关注 1 只" in digest
    assert "买入" in digest


def test_radar_ai_hint_cache_roundtrip(tmp_path, monkeypatch) -> None:
    from vnpy_ashare.quotes.radar_ai_cache import get_cached_hint, put_cached_hint, resolve_ai_hint

    monkeypatch.setattr("vnpy_ashare.quotes.radar_ai_cache._db_path", lambda: tmp_path / "cache.db")
    put_cached_hint("outlook_horizon", variant="watch_next", fingerprint="abc", hint="摘要：关注 3 只")
    assert get_cached_hint("outlook_horizon", variant="watch_next", fingerprint="abc") == "摘要：关注 3 只"
    resolved = resolve_ai_hint(
        "outlook_horizon",
        variant="watch_next",
        fingerprint="xyz",
        digest="摘要：新数据",
    )
    assert resolved == "摘要：新数据"

