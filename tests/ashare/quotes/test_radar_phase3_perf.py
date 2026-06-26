"""雷达阶段 3 性能：候选池缓存、情绪 peek、盘中快照复用。"""

from __future__ import annotations

import pytest

from vnpy_ashare.domain.screener.result_row import ScreenerResultRow
from vnpy_ashare.quotes.radar.loaders.scheduled_intraday import volume_hits_from_intraday_run
from vnpy_ashare.quotes.radar.radar_catalog import RADAR_CARD_BY_ID
from vnpy_ashare.quotes.radar.radar_leader_pool_cache import (
    invalidate_leader_candidate_pool,
    peek_leader_candidate_pool,
    store_leader_candidate_pool,
)
from vnpy_ashare.quotes.radar.radar_loaders import load_discovery_volume_surge, load_radar_card
from vnpy_ashare.screener.run.run_store import ScreenerRunRecord


def test_leader_candidate_pool_cache_roundtrip() -> None:
    invalidate_leader_candidate_pool()
    store_leader_candidate_pool(
        variant="mainline",
        pool_size=40,
        candidates=[{"vt_symbol": "600000.SSE", "change_pct": 5.0}],
        total=100,
    )
    peeked = peek_leader_candidate_pool(variant="mainline", pool_size=40)
    assert peeked is not None
    candidates, total = peeked
    assert total == 100
    assert candidates[0]["vt_symbol"] == "600000.SSE"
    assert peek_leader_candidate_pool(variant="all_market", pool_size=40) is None


def test_build_leader_candidate_pool_uses_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    from vnpy_ashare.quotes.radar import radar_leader_pick as mod

    invalidate_leader_candidate_pool()
    calls: list[int] = []

    def _fake_snapshot() -> None:
        calls.append(1)
        raise AssertionError("不应重复加载行情快照")

    monkeypatch.setattr(mod, "load_screening_quote_snapshot", _fake_snapshot)
    store_leader_candidate_pool(
        variant="mainline",
        pool_size=40,
        candidates=[{"vt_symbol": "600000.SSE"}],
        total=50,
    )
    candidates, total = mod.build_leader_candidate_pool(variant="mainline", pool_size=40)
    assert total == 50
    assert candidates[0]["vt_symbol"] == "600000.SSE"
    assert calls == []


def test_volume_hits_from_intraday_run_filters_dimensions() -> None:
    row_a = ScreenerResultRow.from_mapping(
        {
            "vt_symbol": "600000.SSE",
            "name": "A",
            "dimensions": {"volume_surge": 88.0, "momentum": 70.0},
            "hit_reason": "放量",
        }
    )
    row_b = ScreenerResultRow.from_mapping(
        {
            "vt_symbol": "000001.SZSE",
            "name": "B",
            "dimensions": {"volume_ratio": 75.0},
            "hit_reason": "量比",
        }
    )
    row_c = ScreenerResultRow.from_mapping({"vt_symbol": "000002.SZSE", "name": "C", "dimensions": {"momentum": 90.0}})
    record = ScreenerRunRecord(
        id="run1",
        condition="盘中",
        source="recipe",
        row_count=2,
        total_scanned=3000,
        config={"trigger": "scheduled_intraday"},
        rows=[row_a, row_b, row_c],
        created_at="2026-06-26 10:00:00",
    )
    hits, total = volume_hits_from_intraday_run(record, pool_size=5)
    assert total == 3000
    assert [hit.vt_symbol for hit in hits] == ["600000.SSE", "000001.SZSE"]
    assert hits[0].dimension_id == "volume_surge"
    assert hits[1].dimension_id == "volume_ratio"


def test_load_discovery_volume_surge_prefers_intraday_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    row = ScreenerResultRow.from_mapping(
        {
            "vt_symbol": "600000.SSE",
            "name": "浦发",
            "symbol": "600000",
            "change_pct": 3.0,
            "dimensions": {"volume_surge": 90.0},
            "hit_reason": "放量",
        }
    )
    record = ScreenerRunRecord(
        id="run-intraday",
        condition="盘中自动",
        source="recipe",
        row_count=1,
        total_scanned=4000,
        config={"trigger": "scheduled_intraday"},
        rows=[row],
        created_at="2026-06-26 10:05:00",
    )
    monkeypatch.setattr(
        "vnpy_ashare.quotes.radar.loaders.discovery.peek_fresh_intraday_screen_run",
        lambda **kwargs: record,
    )
    monkeypatch.setattr(
        "vnpy_ashare.quotes.radar.loaders.discovery.run_volume_surge",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("不应全市场扫描")),
    )
    spec = RADAR_CARD_BY_ID["discovery_volume_surge"]
    data = load_discovery_volume_surge(spec)
    assert data.rows
    assert data.rows[0].vt_symbol == "600000.SSE"
    assert "定时快照" in data.subtitle
    assert data.run_id == "run-intraday"


def test_load_market_emotion_peeks_cache_before_fetch(monkeypatch: pytest.MonkeyPatch) -> None:
    from vnpy_ashare.quotes.market.emotion_cycle import EmotionCycleSnapshot

    snapshot = EmotionCycleSnapshot(
        stage="startup",
        stage_label="启动",
        position_pct_min=0.2,
        position_pct_max=0.4,
        position_factor=0.6,
        allow_new_positions=True,
        allowed_modes=("trend",),
        warnings=(),
        inputs={"limit_up_count": 30, "limit_down_count": 5, "max_limit_times": 4, "limit_ladder_depth": 3, "up_ratio": 0.55},
        updated_at="2026-06-26 10:00",
    )
    fetch_calls: list[bool] = []

    def _load(*, fetch_if_missing: bool = False, breadth=None):
        fetch_calls.append(fetch_if_missing)
        return None

    monkeypatch.setattr(
        "vnpy_ashare.quotes.radar.radar_market_emotion.peek_emotion_cycle_snapshot",
        lambda **kwargs: snapshot,
    )
    monkeypatch.setattr(
        "vnpy_ashare.quotes.radar.radar_market_emotion.load_emotion_cycle_snapshot",
        _load,
    )
    data = load_radar_card("market_emotion")
    assert data.rows
    assert data.subtitle.startswith("启动")
    assert fetch_calls == []
