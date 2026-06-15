"""雷达卡片数据加载测试。"""

from vnpy_ashare.quotes.radar.radar_catalog import RADAR_CARD_BY_ID
from vnpy_ashare.quotes.radar.radar_loaders import (
    RadarCardData,
    RadarRow,
    _liquidity_metric,
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
    monkeypatch.setattr("vnpy_ashare.quotes.radar.radar_loaders.get_latest_run", lambda: None)
    spec = RADAR_CARD_BY_ID["screen_latest"]
    data = load_screen_latest(spec)
    assert data.rows == ()
    assert "暂无选股记录" in data.empty_message


def test_load_discovery_moneyflow_intraday_empty(monkeypatch) -> None:
    monkeypatch.setattr(
        "vnpy_ashare.screener.dimensions.moneyflow_resolve.resolve_moneyflow_hits",
        lambda _n, **kwargs: ([], 0, ""),
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
    from vnpy_ashare.quotes.radar.radar_models import merge_row_quotes

    monkeypatch.setattr(
        "vnpy_ashare.quotes.radar.radar_models.get_market_quotes_cache",
        lambda: [{"vt_symbol": "600000.SSE", "amount": 99_000_000, "volume": 12345}],
    )
    merged = merge_row_quotes({"vt_symbol": "600000.SSE", "volume": 0})
    assert merged["amount"] == 99_000_000
    assert merged["volume"] == 12345


def test_load_discovery_moneyflow_fallback(monkeypatch) -> None:
    from vnpy_ashare.quotes.radar.radar_catalog import RADAR_CARD_BY_ID
    from vnpy_ashare.screener.dimensions.base import DimensionHit, rank_score

    monkeypatch.setattr(
        "vnpy_ashare.domain.market_hours.is_ashare_trading_session",
        lambda: False,
    )

    def _fake_resolve(pool_size, **kwargs):
        ranked_row = {
            "vt_symbol": "600000.SSE",
            "symbol": "600000",
            "name": "浦发银行",
            "net_mf_amount": 1000,
            "buy_elg_amount": 900,
            "sell_elg_amount": 100,
            "buy_lg_amount": 800,
            "sell_lg_amount": 200,
            "buy_md_amount": 300,
            "sell_md_amount": 250,
            "moneyflow_source": "tushare",
            "change_pct": 1.0,
            "turnover_rate": 2.0,
            "last_price": 10.0,
            "flow_kind": "main",
        }
        hit = DimensionHit(
            vt_symbol="600000.SSE",
            dimension_id="moneyflow",
            label="资金",
            weight=1.0,
            score=rank_score(1, 1),
            reason="资金：主力净流入 1,000 万，排名第 1",
            row=ranked_row,
        )
        return [hit], 100, "20260612"

    monkeypatch.setattr(
        "vnpy_ashare.screener.dimensions.moneyflow_resolve.resolve_moneyflow_hits",
        _fake_resolve,
    )
    data = load_discovery_moneyflow_intraday(RADAR_CARD_BY_ID["discovery_moneyflow_intraday"])
    assert len(data.rows) == 1
    assert data.rows[0].metric_label == "主力净流入"
    assert data.rows[0].sub_label == "主力"
    assert "Tushare 20260612" in data.subtitle


def test_load_discovery_volume_surge_keeps_surge_when_ratio_empty(monkeypatch) -> None:
    from vnpy_ashare.quotes.radar.radar_catalog import RADAR_CARD_BY_ID
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
            "name": "浦发银行",
            "symbol": "600000",
            "last_price": 10.0,
            "change_pct": 2.0,
            "volume": 0,
            "amount": 80_000_000,
            "total_mv": 600_000,
        },
    )
    monkeypatch.setattr(
        "vnpy_ashare.quotes.radar.radar_loaders.run_volume_surge",
        lambda _n, weight=1.0: ([surge_hit], 5512),
    )
    monkeypatch.setattr(
        "vnpy_ashare.quotes.radar.radar_loaders.run_volume_ratio",
        lambda _n, weight=1.0: ([], 5512),
    )
    data = load_discovery_volume_surge(RADAR_CARD_BY_ID["discovery_volume_surge"])
    assert len(data.rows) == 1
    assert data.rows[0].name == "浦发银行"


def test_load_discovery_volume_surge_excludes_st_from_ratio_fallback(monkeypatch) -> None:
    from vnpy_ashare.quotes.radar.radar_catalog import RADAR_CARD_BY_ID
    from vnpy_ashare.screener.dimensions.base import DimensionHit

    st_hit = DimensionHit(
        vt_symbol="300093.SZSE",
        dimension_id="volume_ratio",
        label="量比",
        weight=1.0,
        score=100.0,
        reason="test",
        row={
            "vt_symbol": "300093.SZSE",
            "name": "金刚",
            "symbol": "300093",
            "volume_ratio": 5.86,
            "change_pct": -9.26,
            "last_price": 20.87,
        },
    )
    normal_hit = DimensionHit(
        vt_symbol="603014.SSE",
        dimension_id="volume_ratio",
        label="量比",
        weight=1.0,
        score=98.0,
        reason="test",
        row={
            "vt_symbol": "603014.SSE",
            "name": "威高血净",
            "symbol": "603014",
            "volume_ratio": 5.92,
            "change_pct": 10.0,
            "last_price": 42.0,
            "amount": 80_000_000,
            "total_mv": 600_000,
        },
    )
    monkeypatch.setattr(
        "vnpy_ashare.quotes.radar.radar_loaders.run_volume_surge",
        lambda _n, weight=1.0: ([st_hit], 5512),
    )
    monkeypatch.setattr(
        "vnpy_ashare.quotes.radar.radar_loaders.run_volume_ratio",
        lambda _n, weight=1.0: ([st_hit, normal_hit], 5512),
    )
    monkeypatch.setattr(
        "vnpy_ashare.quotes.radar.radar_loaders.name_map_for_symbols",
        lambda _symbols: {"300093.SZSE": "*ST金刚", "603014.SSE": "威高血净"},
    )
    data = load_discovery_volume_surge(RADAR_CARD_BY_ID["discovery_volume_surge"])
    assert [row.vt_symbol for row in data.rows] == ["603014.SSE"]


def test_load_radar_card_unknown() -> None:
    import pytest

    with pytest.raises(ValueError, match="未知雷达卡片"):
        from vnpy_ashare.quotes.radar.radar_loaders import load_radar_card

        load_radar_card("not_exists")


def test_load_watchlist_intraday_empty_pool(monkeypatch) -> None:
    from vnpy_ashare.quotes.radar.radar_watchlist import load_watchlist_intraday

    monkeypatch.setattr(
        "vnpy_ashare.quotes.radar.radar_watchlist.collect_personal_vt_symbols",
        lambda max_items=50: [],
    )
    spec = RADAR_CARD_BY_ID["watchlist_intraday"]
    data = load_watchlist_intraday(spec)
    assert data.rows == ()
    assert "自选池为空" in data.empty_message


def test_watchlist_moneyflow_metric() -> None:
    from vnpy_ashare.quotes.radar.radar_moneyflow import watchlist_moneyflow_metric

    label, value, sub_label, sub_value = watchlist_moneyflow_metric({"vt_symbol": "600000.SSE", "net_mf_amount": 12345, "change_pct": 1.2})
    assert label == "主力净流入"
    assert "12,345" in value
    assert sub_label == "涨幅"


def test_load_watchlist_intraday_fallback_rank(monkeypatch) -> None:
    from vnpy_ashare.quotes.radar.radar_watchlist import load_watchlist_intraday

    monkeypatch.setattr(
        "vnpy_ashare.quotes.radar.radar_watchlist.collect_personal_vt_symbols",
        lambda max_items=50: ["600000.SSE", "000001.SZSE"],
    )
    monkeypatch.setattr(
        "vnpy_ashare.quotes.radar.radar_watchlist.compute_signal_transitions",
        lambda *args, **kwargs: {},
    )
    monkeypatch.setattr(
        "vnpy_ashare.quotes.radar.radar_watchlist._quotes_for_candidates",
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
        "vnpy_ashare.quotes.radar.radar_watchlist.enrich_quotes_with_moneyflow",
        lambda quotes_by_vt, **kwargs: quotes_by_vt,
    )
    spec = RADAR_CARD_BY_ID["watchlist_intraday"]
    data = load_watchlist_intraday(spec)
    assert len(data.rows) == 2
    assert "涨跌幅前列" in data.subtitle


def test_classify_scenario_hint_picks_highest_match(monkeypatch) -> None:
    from vnpy_ashare.domain.signal_snapshot import SignalSnapshot
    from vnpy_ashare.quotes.radar.radar_horizon_scenario import ScenarioMetrics, classify_scenario_hint

    snapshot = SignalSnapshot(
        vt_symbol="600000.SSE",
        strategy_id="AshareDoubleMaStrategy",
        as_of="2025-01-01",
        signal="buy",
        signal_label="买入",
        signal_date=None,
        ref_buy_price=9.5,
        ref_sell_price=None,
        strength=72.0,
        reason_summary="",
        reasons=(),
        warnings=(),
        last_close=10.0,
        action_ref_buy_price=None,
        action_ref_sell_price=None,
        fast_ma=10.2,
        slow_ma=9.8,
        volume_ratio_5d=1.3,
        ma_gap_pct=None,
        strength_cross=None,
        strength_alignment=None,
        strength_volume=None,
        strength_pattern=None,
        relative_index_pct=None,
    )
    metrics = ScenarioMetrics(
        snapshot=snapshot,
        momentum_pct=3.0,
        daily_vol_pct=2.5,
        band_move_pct=5.0,
        band_lower=9.0,
        band_upper=11.0,
    )

    def _matches(_metrics: ScenarioMetrics, *, variant: str) -> bool:
        return variant in ("scenario_bull", "scenario_volatile")

    monkeypatch.setattr(
        "vnpy_ashare.quotes.radar.radar_horizon_scenario.matches_scenario",
        _matches,
    )
    monkeypatch.setattr(
        "vnpy_ashare.quotes.radar.radar_horizon_scenario.bullish_score",
        lambda _metrics: 50.0,
    )
    monkeypatch.setattr(
        "vnpy_ashare.quotes.radar.radar_horizon_scenario.volatility_score",
        lambda _metrics: 30.0,
    )
    assert classify_scenario_hint(metrics) == "偏多"


def test_load_watchlist_intraday_with_scenario_hint(monkeypatch) -> None:
    from vnpy_ashare.quotes.radar.radar_watchlist import load_watchlist_intraday

    monkeypatch.setattr(
        "vnpy_ashare.quotes.radar.radar_watchlist.collect_personal_vt_symbols",
        lambda max_items=50: ["600000.SSE"],
    )
    monkeypatch.setattr(
        "vnpy_ashare.quotes.radar.radar_watchlist.compute_signal_transitions",
        lambda *args, **kwargs: {},
    )
    monkeypatch.setattr(
        "vnpy_ashare.quotes.radar.radar_watchlist._quotes_for_candidates",
        lambda _candidates: {
            "600000.SSE": {
                "vt_symbol": "600000.SSE",
                "symbol": "600000",
                "name": "浦发",
                "last_price": 10.0,
                "change_pct": 3.2,
                "volume_ratio": 1.5,
            },
        },
    )
    monkeypatch.setattr(
        "vnpy_ashare.quotes.radar.radar_watchlist.enrich_quotes_with_moneyflow",
        lambda quotes_by_vt, **kwargs: quotes_by_vt,
    )
    monkeypatch.setattr(
        "vnpy_ashare.quotes.radar.radar_watchlist._compute_scenario_hints",
        lambda _symbols, config=None: {"600000.SSE": "偏多"},
    )
    spec = RADAR_CARD_BY_ID["watchlist_intraday"]
    data = load_watchlist_intraday(spec)
    assert len(data.rows) == 1
    assert data.rows[0].sub_label == "5日情景"
    assert data.rows[0].sub_value == "偏多"
    assert "5日情景 1" in data.subtitle
    assert "5日统计情景" in data.ai_hint


def test_load_sector_theme_empty(monkeypatch) -> None:
    from vnpy_ashare.quotes.radar.radar_sector import load_sector_theme

    monkeypatch.setattr(
        "vnpy_ashare.quotes.radar.radar_sector.run_sector_strength",
        lambda _n, weight=1.0: ([], 0),
    )
    spec = RADAR_CARD_BY_ID["sector_theme"]
    data = load_sector_theme(spec)
    assert data.rows == ()
    assert "板块主线" in data.empty_message


def test_load_outlook_watch_no_cache(monkeypatch) -> None:
    from vnpy_ashare.quotes.radar.radar_horizon import load_outlook_horizon

    monkeypatch.setattr(
        "vnpy_ashare.quotes.radar.radar_horizon.get_horizon_cache",
        lambda _variant: None,
    )
    spec = RADAR_CARD_BY_ID["outlook_watch"]
    data = load_outlook_horizon(spec, force_recompute=False)
    assert data.rows == ()
    assert "展望快照" in data.empty_message


def test_enrich_radar_rows_from_screening_snapshot(monkeypatch) -> None:
    from types import SimpleNamespace

    from vnpy_ashare.quotes.radar.radar_models import RadarRow, enrich_radar_rows

    monkeypatch.setattr("vnpy_ashare.quotes.radar.radar_models.quote_map", lambda: {})
    monkeypatch.setattr(
        "vnpy_ashare.quotes.radar.radar_models.load_screening_quote_snapshot",
        lambda: SimpleNamespace(
            rows=[
                {
                    "vt_symbol": "601916.SSE",
                    "symbol": "601916",
                    "name": "浙商银行",
                    "last_price": 3.21,
                    "change_pct": -0.62,
                }
            ]
        ),
    )
    rows = (
        RadarRow(
            vt_symbol="601916.SSE",
            name="浙商银行",
            symbol="601916",
            price=None,
            change_pct=None,
            metric_label="买入",
            metric_value="78",
            sub_label="事件",
            sub_value="—",
        ),
    )
    enriched = enrich_radar_rows(rows)
    assert enriched[0].price == 3.21
    assert enriched[0].change_pct == -0.62


def test_load_outlook_watch_enriches_cached_rows(monkeypatch) -> None:
    from vnpy_ashare.quotes.radar.radar_horizon import load_outlook_horizon
    from vnpy_ashare.quotes.radar.radar_horizon_cache import HorizonCacheEntry
    from vnpy_ashare.quotes.radar.radar_models import RadarRow

    cached_row = RadarRow(
        vt_symbol="601916.SSE",
        name="浙商银行",
        symbol="601916",
        price=None,
        change_pct=None,
        metric_label="买入",
        metric_value="78",
        sub_label="事件",
        sub_value="—",
    )
    monkeypatch.setattr(
        "vnpy_ashare.quotes.radar.radar_horizon.get_horizon_cache",
        lambda _variant: HorizonCacheEntry(
            variant="watch_next",
            rows=(cached_row,),
            scanned_total=5512,
            excluded_count=4,
            prefilter_total=600,
            refined_total=600,
            kline_missing=0,
            strategy_key="test",
            computed_at="2026-06-13 16:00",
        ),
    )
    monkeypatch.setattr(
        "vnpy_ashare.quotes.radar.radar_horizon.enrich_radar_rows",
        lambda rows: tuple(
            RadarRow(
                vt_symbol=row.vt_symbol,
                name=row.name,
                symbol=row.symbol,
                price=3.21,
                change_pct=-0.62,
                metric_label=row.metric_label,
                metric_value=row.metric_value,
                sub_label=row.sub_label,
                sub_value=row.sub_value,
            )
            for row in rows
        ),
    )
    spec = RADAR_CARD_BY_ID["outlook_watch"]
    data = load_outlook_horizon(spec, force_recompute=False)
    assert len(data.rows) == 1
    assert data.rows[0].price == 3.21
    assert data.rows[0].change_pct == -0.62


def test_build_outlook_ai_prompt() -> None:
    from vnpy_ashare.quotes.radar.radar_horizon import build_outlook_ai_prompt

    payload = {
        "outlook_watch": RadarCardData(
            "outlook_watch",
            "未来·关注",
            "约 5 日窗口",
            (_sample_row("600000.SSE", name="浦发"),),
            "",
            "",
        ),
    }
    prompt = build_outlook_ai_prompt(payload, card_id="outlook_watch")
    assert "非涨跌预测" in prompt
    assert "浦发" in prompt


def test_build_radar_card_ai_prompt_watchlist() -> None:
    from vnpy_ashare.quotes.radar.radar_loaders import build_radar_card_ai_prompt

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
    assert "5 日统计情景" in prompt
    assert "信号跃迁" in prompt
    assert "浦发" in prompt


def test_transition_label() -> None:
    from vnpy_ashare.domain.signal_snapshot import SignalSnapshot
    from vnpy_ashare.quotes.radar.radar_signals import transition_label

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
    from vnpy_ashare.quotes.radar.radar_horizon import build_outlook_digest

    rows = (
        RadarRow(
            "600000.SSE",
            "浦发",
            "600000",
            10.0,
            1.0,
            "买入",
            "72",
            "5日情景",
            "偏多",
        ),
    )
    digest = build_outlook_digest(rows, variant="watch_next")
    assert "关注 1 只" in digest
    assert "买入" in digest


def test_radar_ai_hint_cache_roundtrip(tmp_path, monkeypatch) -> None:
    from vnpy_ashare.quotes.radar.radar_ai_cache import get_cached_hint, put_cached_hint, resolve_ai_hint

    monkeypatch.setattr("vnpy_ashare.quotes.radar.radar_ai_cache._db_path", lambda: tmp_path / "cache.db")
    put_cached_hint("outlook_watch", variant="", fingerprint="abc", hint="摘要：关注 3 只")
    assert get_cached_hint("outlook_watch", variant="", fingerprint="abc") == "摘要：关注 3 只"
    resolved = resolve_ai_hint(
        "outlook_watch",
        variant="",
        fingerprint="xyz",
        digest="摘要：新数据",
    )
    assert resolved == "摘要：新数据"


def test_row_from_dict_uses_universe_name_when_row_missing_name(monkeypatch) -> None:
    from vnpy_ashare.quotes.radar.radar_loaders import _row_from_dict

    monkeypatch.setattr(
        "vnpy_ashare.quotes.radar.radar_loaders.merge_row_quotes",
        lambda row: dict(row),
    )
    monkeypatch.setattr(
        "vnpy_ashare.quotes.radar.radar_loaders.name_map_for_symbols",
        lambda _symbols: {"920083.BSE": "某北交所标的"},
    )
    row = _row_from_dict({"vt_symbol": "920083.BSE", "symbol": "920083"}, name_map={"920083.BSE": "某北交所标的"})
    assert row is not None
    assert row.name == "某北交所标的"
    assert row.symbol == "920083"


def test_row_from_dict_falls_back_to_symbol_not_vt_symbol(monkeypatch) -> None:
    from vnpy_ashare.quotes.radar.radar_loaders import _row_from_dict

    monkeypatch.setattr(
        "vnpy_ashare.quotes.radar.radar_loaders.merge_row_quotes",
        lambda row: dict(row),
    )
    row = _row_from_dict({"vt_symbol": "920083.BSE", "symbol": "920083"}, name_map={})
    assert row is not None
    assert row.name == "920083"


def test_incremental_refresh_radar_card_quotes(monkeypatch) -> None:
    from vnpy_ashare.quotes.radar.radar_loaders import incremental_refresh_radar_card_quotes

    original_row = _sample_row("600000.SSE", name="浦发")
    data = RadarCardData(
        "discovery_volume_surge",
        "发现·放量",
        "Top 8",
        (original_row,),
        "",
        "",
    )
    monkeypatch.setattr(
        "vnpy_ashare.quotes.radar.radar_models.enrich_radar_rows",
        lambda rows: tuple(
            RadarRow(
                vt_symbol=row.vt_symbol,
                name=row.name,
                symbol=row.symbol,
                price=11.5,
                change_pct=3.2,
                metric_label=row.metric_label,
                metric_value=row.metric_value,
                sub_label=row.sub_label,
                sub_value=row.sub_value,
            )
            for row in rows
        ),
    )
    refreshed = incremental_refresh_radar_card_quotes(data)
    assert refreshed.subtitle == "Top 8"
    assert refreshed.rows[0].price == 11.5
    assert refreshed.rows[0].change_pct == 3.2
    assert refreshed.rows[0].metric_value == original_row.metric_value
