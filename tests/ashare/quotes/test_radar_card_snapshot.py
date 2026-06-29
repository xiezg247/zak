"""雷达卡片磁盘快照与预热任务测试。"""

from __future__ import annotations

import pytest

from vnpy_ashare.quotes.radar.loaders import RadarCardData, RadarRow
from vnpy_ashare.quotes.radar.radar_card_snapshot_cache import (
    invalidate_radar_card_snapshots,
    peek_radar_card_snapshot,
    put_radar_card_snapshot,
    radar_card_variant_key,
)


def _sample_card(card_id: str = "market_emotion") -> RadarCardData:
    return RadarCardData(
        card_id=card_id,
        title="盘面·环境",
        subtitle="启动",
        rows=(
            RadarRow(
                vt_symbol="__stat__:stage",
                name="情绪阶段",
                symbol="",
                price=None,
                change_pct=None,
                metric_label="阶段",
                metric_value="启动",
                sub_label="仓位",
                sub_value="30%",
            ),
        ),
        empty_message="",
        updated_at="2026-06-26 10:00",
        total_count=1,
    )


def test_radar_card_snapshot_put_and_peek() -> None:
    invalidate_radar_card_snapshots()
    data = _sample_card()
    put_radar_card_snapshot("market_emotion", data, variant_key="")
    peeked = peek_radar_card_snapshot("market_emotion", variant_key="")
    assert peeked is not None
    assert peeked.card_id == "market_emotion"
    assert peeked.rows[0].metric_value == "启动"


def test_radar_card_variant_key_per_card() -> None:
    variants = {
        "leader_pick_variant": "all_market",
        "sector_variant": "concept_leaders",
        "sector_flow_hot_variant": "concept",
        "limit_ladder_variant": "by_sector",
    }
    assert radar_card_variant_key("leader_pick", variants) == "all_market"
    assert radar_card_variant_key("discovery_limit_ladder", variants) == "by_sector"
    assert radar_card_variant_key("market_emotion", variants) == ""


def test_load_radar_card_item_reads_disk_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    from vnpy_ashare.quotes.radar.loaders import load as load_mod

    invalidate_radar_card_snapshots()
    cached = _sample_card("leader_pick")
    put_radar_card_snapshot("leader_pick", cached, variant_key="mainline")

    monkeypatch.setattr(
        load_mod,
        "load_radar_card_uncached",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("不应重算")),
    )
    variants = load_mod._radar_load_variants(leader_pick_variant="mainline")
    card_id, data, error = load_mod._load_radar_card_item(("leader_pick", {}), variants=variants)
    assert error is None
    assert data is not None
    assert card_id == "leader_pick"
    assert data.subtitle == "启动"


def test_warm_radar_card_snapshots_skips_off_session(monkeypatch: pytest.MonkeyPatch) -> None:
    from vnpy_ashare.jobs.radar.card_snapshot_warmup import warm_radar_card_snapshots_job

    monkeypatch.setattr(
        "vnpy_ashare.jobs.radar.card_snapshot_warmup.is_ashare_trading_session",
        lambda _now: False,
    )
    result = warm_radar_card_snapshots_job()
    assert result.skipped is True
