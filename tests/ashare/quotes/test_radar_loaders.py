"""雷达卡片数据加载测试。"""

import pytest

from vnpy_ashare.quotes.radar.loaders import (
    RadarCardData,
    RadarRow,
    build_radar_resonance_list,
    compute_radar_resonance,
    incremental_refresh_radar_card_quotes,
    load_discovery_moneyflow_intraday,
    load_discovery_volume_surge,
    load_radar_card,
    load_screen_task,
)
from vnpy_ashare.quotes.radar.radar_catalog import RADAR_CARD_BY_ID


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


def _sample_card(
    card_id: str,
    title: str,
    *,
    subtitle: str = "",
    rows: tuple[RadarRow, ...] = (),
    **kwargs: object,
) -> RadarCardData:
    return RadarCardData(
        card_id=card_id,
        title=title,
        subtitle=subtitle,
        rows=rows,
        empty_message="",
        updated_at="",
        **kwargs,
    )


def test_load_screen_task_latest_empty(monkeypatch) -> None:
    from vnpy_ashare.domain.radar.catalog import RadarCardSpec

    monkeypatch.setattr("vnpy_ashare.quotes.radar.loaders.screener.get_latest_run", lambda: None)
    spec = RadarCardSpec(id="screen_task", title="选股结果·任务", category="screen")
    data = load_screen_task(spec, variant="latest")
    assert data.rows == ()
    assert "暂无选股记录" in data.empty_message


def test_load_discovery_moneyflow_intraday_empty(monkeypatch) -> None:
    monkeypatch.setattr(
        "vnpy_ashare.quotes.radar.loaders.discovery.resolve_moneyflow_hits",
        lambda _n, **kwargs: ([], 0, ""),
    )
    spec = RADAR_CARD_BY_ID["discovery_moneyflow_intraday"]
    data = load_discovery_moneyflow_intraday(spec)
    assert data.rows == ()
    assert "暂无行情数据" in data.empty_message


def test_compute_radar_resonance() -> None:
    payload = {
        "a": _sample_card("a", "卡A", rows=(_sample_row("600000.SSE"),)),
        "b": _sample_card("b", "卡B", rows=(_sample_row("600000.SSE"), _sample_row("000001.SZSE"))),
    }
    assert compute_radar_resonance(payload) == {"600000.SSE": 2}


def test_build_radar_resonance_list() -> None:
    payload = {
        "a": _sample_card("a", "选股", rows=(_sample_row("600000.SSE", name="浦发"),)),
        "b": _sample_card(
            "b",
            "发现",
            rows=(_sample_row("600000.SSE", name="浦发"), _sample_row("000001.SZSE", name="平安")),
        ),
    }
    entries = build_radar_resonance_list(payload)
    assert len(entries) == 1
    assert entries[0].vt_symbol == "600000.SSE"
    assert entries[0].card_count == 2


def test_load_discovery_moneyflow_fallback(monkeypatch) -> None:
    from vnpy_ashare.screener.dimensions.base import DimensionHit, rank_score

    monkeypatch.setattr(
        "vnpy_ashare.domain.time.market_hours.is_ashare_trading_session",
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
        "vnpy_ashare.quotes.radar.loaders.discovery.resolve_moneyflow_hits",
        _fake_resolve,
    )
    data = load_discovery_moneyflow_intraday(RADAR_CARD_BY_ID["discovery_moneyflow_intraday"])
    assert len(data.rows) == 1
    assert data.rows[0].metric_label == "主力净流入"
    assert "Tushare 20260612" in data.subtitle


def test_load_discovery_volume_surge_excludes_st_from_ratio_fallback(monkeypatch) -> None:
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
        "vnpy_ashare.quotes.radar.loaders.discovery.run_volume_surge",
        lambda _n, weight=1.0: ([st_hit], 5512),
    )
    monkeypatch.setattr(
        "vnpy_ashare.quotes.radar.loaders.discovery.run_volume_ratio",
        lambda _n, weight=1.0: ([st_hit, normal_hit], 5512),
    )
    monkeypatch.setattr(
        "vnpy_ashare.quotes.radar.loaders.discovery.name_map_for_symbols",
        lambda _symbols: {"300093.SZSE": "*ST金刚", "603014.SSE": "威高血净"},
    )
    data = load_discovery_volume_surge(RADAR_CARD_BY_ID["discovery_volume_surge"])
    assert [row.vt_symbol for row in data.rows] == ["603014.SSE"]


def test_load_radar_card_unknown() -> None:
    with pytest.raises(ValueError, match="未知雷达卡片"):
        load_radar_card("not_exists")


def test_enrich_radar_rows_from_screening_snapshot(monkeypatch) -> None:
    from types import SimpleNamespace

    from vnpy_ashare.quotes.radar.radar_models import enrich_radar_rows

    monkeypatch.setattr("vnpy_ashare.quotes.radar.radar_models.quote_map", lambda: {})
    monkeypatch.setattr("vnpy_ashare.quotes.radar.radar_models.is_ashare_trading_session", lambda: False)
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


def test_incremental_refresh_radar_card_quotes(monkeypatch) -> None:
    original_row = _sample_row("600000.SSE", name="浦发")
    data = _sample_card(
        "discovery_volume_surge",
        "发现·放量",
        subtitle="Top 8",
        rows=(original_row,),
    )
    monkeypatch.setattr(
        "vnpy_ashare.quotes.radar.radar_models.refresh_radar_rows_live_quotes",
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
